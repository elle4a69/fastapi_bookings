import React, { useState, useMemo, useRef } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Network,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Search,
  AlertCircle,
  Info,
  RefreshCw,
} from 'lucide-react';
import type { EpistemicGraphData, GraphNode, ProviderItem } from '../types';

interface EpistemicGraphCanvasProps {
  graphData: EpistemicGraphData | null;
  isLoading: boolean;
  selectedProvider: ProviderItem | null;
  onSelectNode: (node: GraphNode) => void;
  onRefresh: () => void;
}

export const EpistemicGraphCanvas: React.FC<EpistemicGraphCanvasProps> = ({
  graphData,
  isLoading,
  selectedProvider,
  onSelectNode,
  onRefresh,
}) => {
  const [zoom, setZoom] = useState<number>(1);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string>('all');
  const [selectedScopeFilter, setSelectedScopeFilter] = useState<'all' | 'shared' | 'provider'>('all');
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  const canvasRef = useRef<HTMLDivElement>(null);

  // Filtered nodes
  const filteredNodes = useMemo(() => {
    if (!graphData?.nodes) return [];
    return graphData.nodes.filter((node) => {
      // Type filter
      if (selectedTypeFilter !== 'all' && node.type !== selectedTypeFilter) return false;
      // Scope filter
      if (selectedScopeFilter === 'shared' && node.scope !== 'tenant_shared') return false;
      if (selectedScopeFilter === 'provider' && node.scope !== 'provider_private') return false;
      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchLabel = node.label.toLowerCase().includes(q);
        const matchTitle = node.title.toLowerCase().includes(q);
        const matchContent = (node.content || '').toLowerCase().includes(q);
        return matchLabel || matchTitle || matchContent;
      }
      return true;
    });
  }, [graphData?.nodes, selectedTypeFilter, selectedScopeFilter, searchQuery]);

  const activeNodeIds = useMemo(() => new Set(filteredNodes.map((n) => n.id)), [filteredNodes]);

  // Filtered edges
  const filteredEdges = useMemo(() => {
    if (!graphData?.edges) return [];
    return graphData.edges.filter(
      (e) => activeNodeIds.has(e.source) && activeNodeIds.has(e.target)
    );
  }, [graphData?.edges, activeNodeIds]);

  // Compute node layout positions deterministically
  const nodePositions = useMemo(() => {
    const positions: Record<string, { x: number; y: number }> = {};
    if (!graphData?.nodes || graphData.nodes.length === 0) return positions;

    const centerX = 500;
    const centerY = 350;

    // 1. Identify Central Root Node
    const rootNode = graphData.nodes.find((n) => n.type === 'provider' || n.type === 'tenant') || graphData.nodes[0];
    positions[rootNode.id] = { x: centerX, y: centerY };

    // 2. Identify Secondary Nodes (Topics / Categories)
    const topicNodes = graphData.nodes.filter((n) => n.type === 'topic' && n.id !== rootNode.id);
    const otherNodes = graphData.nodes.filter(
      (n) => n.id !== rootNode.id && n.type !== 'topic'
    );

    // Place topic nodes in inner ring
    const innerRadius = 160;
    topicNodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / Math.max(topicNodes.length, 1);
      positions[node.id] = {
        x: centerX + innerRadius * Math.cos(angle),
        y: centerY + innerRadius * Math.sin(angle),
      };
    });

    // Place entity nodes (facts, preferences, policies, etc.) in outer ring or anchored to topics
    const outerRadius = 300;
    otherNodes.forEach((node, i) => {
      // Find edge connecting this node to a topic or root
      const connectedTopicEdge = graphData.edges.find(
        (e) => (e.target === node.id && positions[e.source]) || (e.source === node.id && positions[e.target])
      );
      if (connectedTopicEdge && topicNodes.length > 0) {
        const anchorId = positions[connectedTopicEdge.source] ? connectedTopicEdge.source : connectedTopicEdge.target;
        const anchorPos = positions[anchorId] || { x: centerX, y: centerY };
        // Jitter slightly away from center
        const dirX = anchorPos.x - centerX;
        const dirY = anchorPos.y - centerY;
        const spreadAngle = ((i % 5) - 2) * 0.35;
        const baseAngle = Math.atan2(dirY, dirX) + spreadAngle;
        positions[node.id] = {
          x: centerX + (outerRadius + (i % 2 === 0 ? 30 : -20)) * Math.cos(baseAngle),
          y: centerY + (outerRadius + (i % 2 === 0 ? 30 : -20)) * Math.sin(baseAngle),
        };
      } else {
        const angle = (2 * Math.PI * i) / Math.max(otherNodes.length, 1);
        positions[node.id] = {
          x: centerX + outerRadius * Math.cos(angle),
          y: centerY + outerRadius * Math.sin(angle),
        };
      }
    });

    return positions;
  }, [graphData]);

  // Color mapping based on ontological node type
  const getNodeColor = (type: string, isHovered: boolean) => {
    switch (type) {
      case 'provider':
        return {
          bg: isHovered ? '#6366f1' : '#4f46e5',
          border: '#3730a3',
          text: '#ffffff',
          badge: 'bg-indigo-600 text-white',
        };
      case 'tenant':
        return {
          bg: isHovered ? '#3b82f6' : '#2563eb',
          border: '#1d4ed8',
          text: '#ffffff',
          badge: 'bg-blue-600 text-white',
        };
      case 'topic':
        return {
          bg: isHovered ? '#0ea5e9' : '#0284c7',
          border: '#0369a1',
          text: '#ffffff',
          badge: 'bg-sky-600 text-white',
        };
      case 'preference':
        return {
          bg: isHovered ? '#10b981' : '#059669',
          border: '#047857',
          text: '#ffffff',
          badge: 'bg-emerald-600 text-white',
        };
      case 'boundary':
        return {
          bg: isHovered ? '#ef4444' : '#dc2626',
          border: '#b91c1c',
          text: '#ffffff',
          badge: 'bg-rose-600 text-white',
        };
      case 'policy':
        return {
          bg: isHovered ? '#f59e0b' : '#d97706',
          border: '#b45309',
          text: '#ffffff',
          badge: 'bg-amber-600 text-white',
        };
      case 'behaviour':
        return {
          bg: isHovered ? '#a855f7' : '#9333ea',
          border: '#7e22ce',
          text: '#ffffff',
          badge: 'bg-purple-600 text-white',
        };
      default: // fact
        return {
          bg: isHovered ? '#14b8a6' : '#0d9488',
          border: '#0f766e',
          text: '#ffffff',
          badge: 'bg-teal-600 text-white',
        };
    }
  };

  // Edge label colors
  const getEdgeStroke = (relation: string) => {
    switch (relation) {
      case 'PREFERS':
        return '#10b981';
      case 'AVOIDS':
        return '#ef4444';
      case 'SUPERSEDES':
        return '#94a3b8';
      case 'APPLIES_WHEN':
        return '#f59e0b';
      case 'HAS_BOUNDARY':
        return '#ec4899';
      default:
        return '#64748b';
    }
  };

  return (
    <Card className="border-border shadow-xs overflow-hidden flex flex-col">
      {/* Top Visualizer Control Bar */}
      <div className="p-3.5 border-b bg-muted/20 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="text-primary border-primary/30 text-xs font-semibold gap-1">
            <Network className="h-3.5 w-3.5" />
            Epistemic Graph
          </Badge>

          {/* Node Scope Statistics */}
          <Badge variant="secondary" className="font-mono text-[11px]">
            {filteredNodes.length} Nodes • {filteredEdges.length} Edges
          </Badge>

          <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px] font-mono">
            {graphData?.stats?.provider_nodes || 0} Provider-Private
          </Badge>

          <Badge variant="outline" className="bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30 text-[10px] font-mono">
            {graphData?.stats?.shared_nodes || 0} Tenant-Shared
          </Badge>

          {graphData?.stats?.neo4j_online ? (
            <Badge variant="outline" className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/40 text-[10px] gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Neo4j Live
            </Badge>
          ) : (
            <Badge variant="outline" className="bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/40 text-[10px] gap-1">
              <AlertCircle className="h-3 w-3" />
              Relational Epistemic Mode
            </Badge>
          )}

          {selectedProvider?.id && (
            <Badge variant="outline" className="font-mono text-[10px] bg-muted/50">
              Scope: {selectedProvider.name}
            </Badge>
          )}
        </div>

        {/* Search, Scope Filter, and Zoom Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Node search input */}
          <div className="relative w-44">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search graph..."
              className="h-8 text-xs pl-8"
            />
          </div>

          {/* Type Filter Select */}
          <select
            value={selectedTypeFilter}
            onChange={(e) => setSelectedTypeFilter(e.target.value)}
            className="h-8 text-xs rounded-md border border-input bg-background px-2.5 py-1 text-foreground"
          >
            <option value="all">All Types</option>
            <option value="provider">Provider Root</option>
            <option value="topic">Topic / Category</option>
            <option value="fact">Durable Fact</option>
            <option value="preference">Preference</option>
            <option value="behaviour">Behavioural Rule</option>
            <option value="policy">Policy</option>
            <option value="boundary">Boundary</option>
          </select>

          {/* Scope Filter Buttons */}
          <div className="flex items-center rounded-md border p-0.5 bg-background text-xs">
            <button
              onClick={() => setSelectedScopeFilter('all')}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                selectedScopeFilter === 'all' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setSelectedScopeFilter('provider')}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                selectedScopeFilter === 'provider' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'
              }`}
            >
              Provider
            </button>
            <button
              onClick={() => setSelectedScopeFilter('shared')}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                selectedScopeFilter === 'shared' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'
              }`}
            >
              Shared
            </button>
          </div>

          {/* Zoom Actions */}
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => setZoom((z) => Math.max(0.5, z - 0.15))}
              title="Zoom Out"
            >
              <ZoomOut className="h-3.5 w-3.5" />
            </Button>
            <span className="text-xs font-mono w-10 text-center text-muted-foreground">
              {Math.round(zoom * 100)}%
            </span>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => setZoom((z) => Math.min(2.0, z + 0.15))}
              title="Zoom In"
            >
              <ZoomIn className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => setZoom(1)}
              title="Reset Zoom"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={onRefresh}
              disabled={isLoading}
              title="Refresh Graph"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </div>

      {/* SVG Canvas Area */}
      <div
        ref={canvasRef}
        className="relative w-full h-[540px] bg-slate-950/95 overflow-hidden select-none cursor-grab active:cursor-grabbing border-b"
      >
        {/* Background Grid Pattern */}
        <div
          className="absolute inset-0 opacity-15 pointer-events-none"
          style={{
            backgroundImage: `radial-gradient(circle, #64748b 1px, transparent 1px)`,
            backgroundSize: `${30 * zoom}px ${30 * zoom}px`,
          }}
        />

        <svg
          className="w-full h-full"
          viewBox="0 0 1000 700"
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: '500px 350px',
            transition: 'transform 0.15s ease-out',
          }}
        >
          <defs>
            {/* Arrow marker for edges */}
            <marker
              id="arrowhead"
              markerWidth="8"
              markerHeight="6"
              refX="18"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 8 3, 0 6" fill="#64748b" />
            </marker>
            <marker
              id="arrowhead-prefers"
              markerWidth="8"
              markerHeight="6"
              refX="18"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 8 3, 0 6" fill="#10b981" />
            </marker>
            <marker
              id="arrowhead-supersedes"
              markerWidth="8"
              markerHeight="6"
              refX="18"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 8 3, 0 6" fill="#94a3b8" />
            </marker>
          </defs>

          {/* Render Directed Edges */}
          <g className="edges">
            {filteredEdges.map((edge) => {
              const src = nodePositions[edge.source];
              const tgt = nodePositions[edge.target];
              if (!src || !tgt) return null;

              const isHighlighted = hoveredNodeId === edge.source || hoveredNodeId === edge.target;
              const strokeColor = getEdgeStroke(edge.relation);
              const markerId =
                edge.relation === 'PREFERS'
                  ? 'url(#arrowhead-prefers)'
                  : edge.relation === 'SUPERSEDES'
                  ? 'url(#arrowhead-supersedes)'
                  : 'url(#arrowhead)';

              const midX = (src.x + tgt.x) / 2;
              const midY = (src.y + tgt.y) / 2;

              return (
                <g key={edge.id} className="transition-opacity">
                  <line
                    x1={src.x}
                    y1={src.y}
                    x2={tgt.x}
                    y2={tgt.y}
                    stroke={strokeColor}
                    strokeWidth={isHighlighted ? 2.5 : 1.2}
                    strokeOpacity={isHighlighted ? 0.9 : 0.4}
                    strokeDasharray={edge.relation === 'SUPERSEDES' ? '4 3' : 'none'}
                    markerEnd={markerId}
                  />
                  {/* Edge label pill */}
                  <rect
                    x={midX - 30}
                    y={midY - 9}
                    width="60"
                    height="18"
                    rx="4"
                    fill="#0f172a"
                    stroke={strokeColor}
                    strokeWidth="0.8"
                    strokeOpacity={isHighlighted ? 0.9 : 0.4}
                  />
                  <text
                    x={midX}
                    y={midY + 3.5}
                    textAnchor="middle"
                    fill={strokeColor}
                    fontSize="9"
                    fontFamily="monospace"
                    fontWeight="bold"
                    className="select-none pointer-events-none"
                  >
                    {edge.label}
                  </text>
                </g>
              );
            })}
          </g>

          {/* Render Entity Nodes */}
          <g className="nodes">
            {filteredNodes.map((node) => {
              const pos = nodePositions[node.id];
              if (!pos) return null;

              const isHovered = hoveredNodeId === node.id;
              const colors = getNodeColor(node.type, isHovered);
              const isRoot = node.type === 'provider' || node.type === 'tenant';
              const radius = isRoot ? 38 : node.type === 'topic' ? 28 : 22;

              return (
                <g
                  key={node.id}
                  transform={`translate(${pos.x}, ${pos.y})`}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                  onClick={() => onSelectNode(node)}
                  className="cursor-pointer group"
                >
                  {/* Outer Pulsing Aura on Hover or Root */}
                  {isRoot && (
                    <circle
                      r={radius + 8}
                      fill="none"
                      stroke={colors.bg}
                      strokeWidth="1.5"
                      strokeOpacity="0.4"
                      className="animate-pulse"
                    />
                  )}

                  {/* Main Node Circle */}
                  <circle
                    r={radius}
                    fill={colors.bg}
                    stroke={isHovered ? '#ffffff' : colors.border}
                    strokeWidth={isHovered ? 2.5 : 1.5}
                    className="transition-transform duration-150 drop-shadow-md"
                  />

                  {/* Center Node Icon / Type Abbreviation */}
                  <text
                    textAnchor="middle"
                    dy=".3em"
                    fill={colors.text}
                    fontSize={isRoot ? '12' : '10'}
                    fontWeight="bold"
                    fontFamily="sans-serif"
                    className="pointer-events-none select-none uppercase tracking-wider"
                  >
                    {isRoot ? 'ROOT' : node.type.slice(0, 3)}
                  </text>

                  {/* Node Label Below */}
                  <g transform={`translate(0, ${radius + 14})`}>
                    <rect
                      x="-60"
                      y="-8"
                      width="120"
                      height="16"
                      rx="3"
                      fill="#020617"
                      fillOpacity="0.85"
                      stroke="#334155"
                      strokeWidth="0.5"
                    />
                    <text
                      textAnchor="middle"
                      dy="4"
                      fill="#e2e8f0"
                      fontSize="9.5"
                      fontFamily="sans-serif"
                      fontWeight="500"
                      className="pointer-events-none select-none"
                    >
                      {node.label.length > 18 ? node.label.slice(0, 16) + '...' : node.label}
                    </text>
                  </g>

                  {/* Scope Badge (Provider vs Tenant Shared) */}
                  <g transform={`translate(${radius - 4}, ${-radius + 4})`}>
                    <circle
                      r="6"
                      fill={node.scope === 'provider_private' ? '#10b981' : '#3b82f6'}
                      stroke="#0f172a"
                      strokeWidth="1"
                    />
                  </g>
                </g>
              );
            })}
          </g>
        </svg>

        {/* Canvas Legend & Overlay Help */}
        <div className="absolute bottom-3 left-3 bg-slate-900/90 border border-slate-700/80 p-2.5 rounded-lg text-[10px] text-slate-300 space-y-1.5 backdrop-blur-xs shadow-md">
          <div className="font-semibold text-slate-100 flex items-center gap-1.5">
            <Info className="h-3 w-3 text-primary" />
            Ontology & Scope Legend
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span>Provider-Private</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-blue-500" />
              <span>Tenant-Shared</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-indigo-500" />
              <span>Provider Root</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-teal-500" />
              <span>Durable Fact</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-amber-500" />
              <span>Policy</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-purple-500" />
              <span>Behaviour Guidance</span>
            </div>
          </div>
          <div className="text-[9px] text-slate-400 pt-0.5 border-t border-slate-700/60">
            Click any node to view provenance, scrubbing audit & cache invalidation.
          </div>
        </div>
      </div>
    </Card>
  );
};
