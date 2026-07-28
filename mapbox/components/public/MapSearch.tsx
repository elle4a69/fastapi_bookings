import React, { useEffect, useRef, useState, useCallback } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

// Mapbox public token
mapboxgl.accessToken = 'pk.eyJ1IjoiY2ljY2lvNjQiLCJhIjoiY21yazBxZ21qMDltZDM0b2F1d2xsdDZrbCJ9.WZv80bAtOFDNzXxUZ3RXfw';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TenantPin {
  tenant_id: number;
  business_name: string;
  slug: string;
  latitude: number;
  longitude: number;
  image_url: string | null;
  address?: string;
  status: 'available_today' | 'available_later' | 'unavailable';
  next_available_text: string;
}

interface ServiceOption {
  name: string;
}

// ---------------------------------------------------------------------------
// Status colour mapping
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  available_today: '#10b981',   // emerald-500
  available_later: '#f97316',   // orange-500
  unavailable:     '#ef4444',   // red-500
};

const STATUS_LABELS: Record<string, string> = {
  available_today: 'Available Today',
  available_later: 'Available This Week',
  unavailable:     'Fully Booked',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildPinEl(status: string): HTMLDivElement {
  const container = document.createElement('div');
  container.style.cssText = `
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  `;

  const inner = document.createElement('div');
  const color = STATUS_COLORS[status] ?? '#6b7280';
  inner.style.cssText = `
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: ${color};
    border: 3px solid #fff;
    box-shadow: 0 2px 8px rgba(0,0,0,0.35);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  `;

  container.appendChild(inner);

  container.addEventListener('mouseenter', () => { 
    inner.style.transform = 'scale(1.35)'; 
    inner.style.boxShadow = '0 0 12px ' + color;
  });
  container.addEventListener('mouseleave', () => { 
    inner.style.transform = 'scale(1)'; 
    inner.style.boxShadow = '0 2px 8px rgba(0,0,0,0.35)';
  });

  return container;
}

function buildPopupHtml(pin: TenantPin): string {
  const imgHtml = pin.image_url
    ? `<img src="${pin.image_url}" alt="${pin.business_name}" style="width:100%;height:120px;object-fit:cover;border-radius:8px;margin-bottom:10px;" />`
    : '';
  const badgeColor = STATUS_COLORS[pin.status] ?? '#6b7280';
  const badgeLabel = STATUS_LABELS[pin.status] ?? pin.status;

  return `
    <div style="font-family:'Inter',sans-serif;min-width:210px;padding:4px 0;">
      ${imgHtml}
      <p style="margin:0 0 4px;font-size:15px;font-weight:700;color:#0f172a;">${pin.business_name}</p>
      <span style="display:inline-block;padding:2px 8px;border-radius:999px;font-size:10px;font-weight:600;background:${badgeColor}22;color:${badgeColor};margin-bottom:8px;">${badgeLabel}</span>
      <p style="margin:0 0 12px;font-size:12px;color:#475569;">📅 ${pin.next_available_text}</p>
      <a href="#/book/${pin.slug}"
         style="display:block;text-align:center;padding:8px 0;background:#6366f1;color:#fff;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;transition:background 0.2s;"
         onmouseover="this.style.background='#4f46e5'"
         onmouseout="this.style.background='#6366f1'">
        Book Companion →
      </a>
    </div>
  `;
}

const MAPBOX_STYLES = [
  { name: 'Sleek Dark', url: 'mapbox://styles/mapbox/dark-v11', icon: '⚫' },
  { name: 'Clean Light', url: 'mapbox://styles/mapbox/light-v11', icon: '⚪' },
  { name: 'Streets Map', url: 'mapbox://styles/mapbox/streets-v12', icon: '🏙️' },
  { name: 'Satellite View', url: 'mapbox://styles/mapbox/satellite-streets-v12', icon: '🛰️' },
  { name: 'Outdoors', url: 'mapbox://styles/mapbox/outdoors-v12', icon: '🌲' },
];

const MOCK_COMPANION_PINS: TenantPin[] = [
  {
    tenant_id: 1,
    business_name: 'Bella - Independent Companion',
    slug: 'bella-companion',
    latitude: -37.8136,
    longitude: 144.9665,
    address: '150 Collins St, Melbourne VIC 3000',
    image_url: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&auto=format&fit=crop&q=80',
    status: 'available_today',
    next_available_text: 'Available today at 2:00 PM',
  },
  {
    tenant_id: 2,
    business_name: 'Sarah - Premium Hostess',
    slug: 'sarah-hostess',
    latitude: -37.8250,
    longitude: 144.9700,
    address: '300 St Kilda Rd, Southbank VIC 3006',
    image_url: 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&auto=format&fit=crop&q=80',
    status: 'available_later',
    next_available_text: 'Available tomorrow at 11:00 AM',
  },
  {
    tenant_id: 3,
    business_name: 'Sophie - Elite Companion',
    slug: 'sophie-elite',
    latitude: -37.8000,
    longitude: 144.9680,
    address: '100 Lygon St, Carlton VIC 3053',
    image_url: 'https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=400&auto=format&fit=crop&q=80',
    status: 'unavailable',
    next_available_text: 'Fully booked this week',
  },
  {
    tenant_id: 4,
    business_name: 'Gigi - Independent Companion',
    slug: 'gigi-companion',
    latitude: -37.8390,
    longitude: 144.9950,
    address: '600 Chapel St, South Yarra VIC 3141',
    image_url: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=400&auto=format&fit=crop&q=80',
    status: 'available_today',
    next_available_text: 'Available today at 4:30 PM',
  },
  {
    tenant_id: 5,
    business_name: 'Chloe - Private Escort',
    slug: 'chloe-private',
    latitude: -37.8610,
    longitude: 144.9780,
    address: '120 Fitzroy St, St Kilda VIC 3182',
    image_url: 'https://images.unsplash.com/photo-1488426862026-3ee34a7d66df?w=400&auto=format&fit=crop&q=80',
    status: 'available_later',
    next_available_text: 'Available Friday at 1:00 PM',
  },
  {
    tenant_id: 6,
    business_name: 'Mia - Independent Companion',
    slug: 'mia-companion',
    latitude: -37.8030,
    longitude: 144.9790,
    address: '200 Brunswick St, Fitzroy VIC 3065',
    image_url: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=400&auto=format&fit=crop&q=80',
    status: 'available_today',
    next_available_text: 'Available today at 6:00 PM',
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const MapSearch: React.FC = () => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<mapboxgl.Marker[]>([]);
  const markerMapRef = useRef<Record<number, mapboxgl.Marker>>({});

  const [serviceOptions, setServiceOptions] = useState<ServiceOption[]>([
    { name: 'Incall Booking' },
    { name: 'Outcall Companionship' },
    { name: 'Dinner Hosting' },
    { name: 'VIP Escort' }
  ]);
  const [serviceFilter, setServiceFilter] = useState('');
  const [inputValue, setInputValue] = useState('');
  const [pins, setPins] = useState<TenantPin[]>(MOCK_COMPANION_PINS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mapStyle, setMapStyle] = useState('mapbox://styles/mapbox/dark-v11');

  // Airbnb-style Layout Options: 'split' (Desktop 50/50), 'map-only' (Full Map), 'list-only' (Full List)
  const [layout, setLayout] = useState<'split' | 'map-only' | 'list-only'>('split');
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  // ---------------------------------------------------------------------------
  // Responsive / Viewport Check
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (mobile && layout === 'split') {
        setLayout('list-only'); // On mobile, show list by default
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [layout]);

  // Trigger Map Resize when layout size changes
  useEffect(() => {
    if (mapRef.current) {
      setTimeout(() => {
        mapRef.current?.resize();
      }, 350);
    }
  }, [layout]);

  // ---------------------------------------------------------------------------
  // Fetch service options for the dropdown
  // ---------------------------------------------------------------------------
  useEffect(() => {
    fetch('/api/discovery/services')
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then((data: ServiceOption[]) => {
        if (Array.isArray(data) && data.length > 0) setServiceOptions(data);
      })
      .catch(() => {/* non-critical */ });
  }, []);

  // ---------------------------------------------------------------------------
  // Fetch pins whenever filter changes
  // ---------------------------------------------------------------------------
  const fetchPins = useCallback(async (filter: string) => {
    setLoading(true);
    setError(null);
    const url = filter
      ? `/api/discovery/map?service_type=${encodeURIComponent(filter)}`
      : '/api/discovery/map';
    try {
      const res = await fetch(url);
      if (res.ok) {
        const data: TenantPin[] = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setPins(data);
          setLoading(false);
          return;
        }
      }
    } catch {
      /* fallback to mock dataset */
    }

    // Apply client-side filter to mock dataset
    let filtered = MOCK_COMPANION_PINS;
    if (filter) {
      const lower = filter.toLowerCase();
      filtered = MOCK_COMPANION_PINS.filter(p =>
        p.business_name.toLowerCase().includes(lower) ||
        p.address?.toLowerCase().includes(lower)
      );
    }
    setPins(filtered);
    setLoading(false);
  }, []);

  useEffect(() => { fetchPins(serviceFilter); }, [serviceFilter, fetchPins]);

  // ---------------------------------------------------------------------------
  // Update map style when mapStyle state changes
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (mapRef.current) {
      mapRef.current.setStyle(mapStyle);
    }
  }, [mapStyle]);

  // ---------------------------------------------------------------------------
  // Initialise Mapbox map
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (mapRef.current || !mapContainer.current) return;

    mapRef.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: mapStyle,
      center: [144.9631, -37.8136], // Melbourne default
      zoom: 11,
    });

    mapRef.current.addControl(new mapboxgl.NavigationControl(), 'top-right');
    mapRef.current.addControl(
      new mapboxgl.GeolocateControl({ positionOptions: { enableHighAccuracy: true }, trackUserLocation: false }),
      'top-right',
    );

    // Try to centre on user location
    navigator.geolocation?.getCurrentPosition(pos => {
      mapRef.current?.flyTo({
        center: [pos.coords.longitude, pos.coords.latitude],
        zoom: 12,
        duration: 1800,
      });
    });

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Sync pins → markers whenever pins or map changes
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Remove old markers
    markersRef.current.forEach(m => m.remove());
    markersRef.current = [];
    markerMapRef.current = {};

    pins.forEach(pin => {
      const el = buildPinEl(pin.status);

      // Create the marker
      const marker = new mapboxgl.Marker({ element: el })
        .setLngLat([pin.longitude, pin.latitude])
        .addTo(map);

      // Store in ref maps
      markersRef.current.push(marker);
      markerMapRef.current[pin.tenant_id] = marker;

      // Create detailed popup (close button active)
      const clickPopup = new mapboxgl.Popup({ offset: 16, closeButton: true, maxWidth: '245px' })
        .setHTML(buildPopupHtml(pin));

      // Create simple hover tooltip
      const tooltipPopup = new mapboxgl.Popup({ offset: 16, closeButton: false, closeOnClick: false })
        .setHTML(`<div style="font-family:'Inter',sans-serif;font-size:12px;font-weight:600;padding:4px 8px;color:#1e293b;">${pin.business_name} - ${pin.next_available_text}</div>`);

      let isPopupOpen = false;

      // Event: click to open the detailed booking popup
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        tooltipPopup.remove();
        clickPopup.setLngLat([pin.longitude, pin.latitude]).addTo(map);
        isPopupOpen = true;
      });

      // Event: hover to show simple tooltip
      el.addEventListener('mouseenter', () => {
        if (!isPopupOpen) {
          tooltipPopup.setLngLat([pin.longitude, pin.latitude]).addTo(map);
        }
      });

      // Event: hover leave to hide simple tooltip
      el.addEventListener('mouseleave', () => {
        tooltipPopup.remove();
      });

      // Track click popup close to restore hover tooltip capability
      clickPopup.on('close', () => {
        isPopupOpen = false;
      });
    });

    // Fit bounds if we have pins
    if (pins.length > 0) {
      const bounds = new mapboxgl.LngLatBounds();
      pins.forEach(p => bounds.extend([p.longitude, p.latitude]));
      map.fitBounds(bounds, { padding: 60, maxZoom: 14, duration: 800 });
    }
  }, [pins]);

  // ---------------------------------------------------------------------------
  // Card-Pin Interactive Handlers
  // ---------------------------------------------------------------------------
  const handleCardHover = (tenantId: number, isHovered: boolean) => {
    const marker = markerMapRef.current[tenantId];
    if (!marker) return;

    const el = marker.getElement();
    const inner = el.querySelector('div');
    if (!inner) return;

    const color = inner.style.backgroundColor;

    if (isHovered) {
      inner.style.transform = 'scale(1.5)';
      inner.style.boxShadow = `0 0 16px ${color || '#6366f1'}`;
    } else {
      inner.style.transform = 'scale(1)';
      inner.style.boxShadow = '0 2px 8px rgba(0,0,0,0.35)';
    }
  };

  const handleCardClick = (pin: TenantPin) => {
    if (layout === 'list-only' && isMobile) {
      // Switch view on mobile to show the location
      setLayout('map-only');
    }
    mapRef.current?.flyTo({
      center: [pin.longitude, pin.latitude],
      zoom: 14,
      duration: 1200,
    });
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setServiceFilter(inputValue.trim());
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#090d16', fontFamily: "'Inter', sans-serif" }}>
      
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header style={{
        padding: '16px 24px',
        background: 'linear-gradient(135deg, #0f0b1e 0%, #17122a 100%)',
        boxShadow: '0 2px 16px rgba(0,0,0,0.6)',
        borderBottom: '1px solid rgba(99,102,241,0.2)',
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        flexWrap: 'wrap',
      }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '22px', fontWeight: 800, color: '#f3f4f6', letterSpacing: '-0.4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            ✨ Independent Network
          </h1>
          <p style={{ margin: 0, fontSize: '12px', color: '#a5b4fc' }}>
            Keeping independence independent · Real-time status in Melbourne
          </p>
        </div>

        {/* Search form */}
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '8px', flex: 1, maxWidth: '420px' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <input
              type="text"
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              placeholder="Search companion service (e.g. Incall, Outcall...)"
              list="service-options"
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: '10px',
                border: '1px solid #4f46e5',
                background: 'rgba(255,255,255,0.06)',
                color: '#f3f4f6',
                fontSize: '14px',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
            <datalist id="service-options">
              {serviceOptions.map(s => <option key={s.name} value={s.name} />)}
            </datalist>
          </div>
          <button
            type="submit"
            style={{
              padding: '10px 18px',
              borderRadius: '10px',
              border: 'none',
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              color: '#fff',
              fontWeight: 700,
              fontSize: '14px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              boxShadow: '0 4px 12px rgba(99,102,241,0.3)',
            }}
          >
            Search
          </button>
          {serviceFilter && (
            <button
              type="button"
              onClick={() => { setInputValue(''); setServiceFilter(''); }}
              style={{
                padding: '10px 14px',
                borderRadius: '10px',
                border: '1px solid rgba(99,102,241,0.5)',
                background: 'transparent',
                color: '#a5b4fc',
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              Clear
            </button>
          )}
        </form>

        {/* Desktop Layout Switcher */}
        {!isMobile && (
          <div style={{
            display: 'flex',
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '10px',
            padding: '4px',
          }}>
            {[
              { id: 'split', label: '📊 Split view' },
              { id: 'list-only', label: '📋 List view' },
              { id: 'map-only', label: '🗺️ Map view' }
            ].map(tab => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setLayout(tab.id as any)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: layout === tab.id ? '#6366f1' : 'transparent',
                  color: layout === tab.id ? '#fff' : '#94a3b8',
                  transition: 'all 0.2s',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}
      </header>

      {/* ── Main Layout Body ────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', position: 'relative' }}>
        
        {/* Left Side: Scrollable List of Companions */}
        <div style={{
          width: layout === 'split' ? '50%' : layout === 'list-only' ? '100%' : '0%',
          display: layout === 'map-only' ? 'none' : 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
          background: '#090d16',
          borderRight: '1px solid rgba(255,255,255,0.08)',
          transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          boxSizing: 'border-box',
        }}>
          
          {/* Legend Summary */}
          <div style={{
            padding: '16px 24px 8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid rgba(255,255,255,0.04)',
            background: 'rgba(255,255,255,0.01)',
          }}>
            <span style={{ fontSize: '13px', color: '#94a3b8' }}>
              Showing <strong>{pins.length}</strong> independent companions
            </span>
            <div style={{ display: 'flex', gap: '12px' }}>
              {Object.entries(STATUS_LABELS).map(([key, label]) => (
                <span key={key} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#cbd5e1' }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: STATUS_COLORS[key] }} />
                  {label.split(' ')[1] || label}
                </span>
              ))}
            </div>
          </div>

          {/* Cards Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: layout === 'list-only' ? 'repeat(auto-fill, minmax(320px, 1fr))' : '1fr',
            gap: '16px',
            padding: '24px',
          }}>
            {pins.length === 0 && !loading && (
              <div style={{ textAlign: 'center', color: '#64748b', padding: '40px' }}>
                <p style={{ fontSize: '16px', margin: 0 }}>No companions found matching search filter.</p>
              </div>
            )}
            
            {pins.map(pin => {
              const badgeColor = STATUS_COLORS[pin.status];
              const badgeLabel = STATUS_LABELS[pin.status];
              
              return (
                <div
                  key={pin.tenant_id}
                  onMouseEnter={() => handleCardHover(pin.tenant_id, true)}
                  onMouseLeave={() => handleCardHover(pin.tenant_id, false)}
                  onClick={() => handleCardClick(pin)}
                  style={{
                    background: '#111827',
                    borderRadius: '16px',
                    overflow: 'hidden',
                    border: '1px solid rgba(255,255,255,0.05)',
                    display: 'flex',
                    flexDirection: 'column',
                    cursor: 'pointer',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                    transition: 'transform 0.2s, border-color 0.2s',
                    position: 'relative',
                  }}
                  onMouseOver={(e) => e.currentTarget.style.borderColor = 'rgba(99,102,241,0.4)'}
                  onMouseOut={(e) => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.05)'}
                >
                  <div style={{ display: 'flex', flexDirection: 'row', height: '150px' }}>
                    {/* Companion Portrait Photo */}
                    {pin.image_url && (
                      <div style={{ width: '40%', height: '100%', position: 'relative', overflow: 'hidden' }}>
                        <img
                          src={pin.image_url}
                          alt={pin.business_name}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                      </div>
                    )}

                    {/* Companion Info */}
                    <div style={{
                      width: pin.image_url ? '60%' : '100%',
                      padding: '16px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      boxSizing: 'border-box',
                    }}>
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#f3f4f6' }}>
                            {pin.business_name.split(' - ')[0]}
                          </h3>
                        </div>
                        <p style={{ margin: '4px 0 0', fontSize: '11px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          📍 {pin.address ? pin.address.split(',')[0] : 'Melbourne VIC'}
                        </p>
                        
                        <div style={{ marginTop: '8px' }}>
                          <span style={{
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: '999px',
                            fontSize: '9px',
                            fontWeight: 700,
                            background: badgeColor + '15',
                            color: badgeColor,
                            border: `1px solid ${badgeColor}35`,
                          }}>
                            {badgeLabel}
                          </span>
                        </div>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
                        <span style={{ fontSize: '11px', color: '#a5b4fc', fontWeight: 500 }}>
                          📅 {pin.next_available_text.split('at')[0]}
                        </span>
                        
                        <a
                          href={`#/book/${pin.slug}`}
                          onClick={(e) => e.stopPropagation()}
                          style={{
                            padding: '6px 12px',
                            background: 'linear-gradient(135deg, #6366f1, #4f46e5)',
                            color: '#fff',
                            borderRadius: '8px',
                            fontSize: '11px',
                            fontWeight: 700,
                            textDecoration: 'none',
                            boxShadow: '0 2px 6px rgba(99,102,241,0.2)',
                          }}
                        >
                          Book Now
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Side: Map Panel */}
        <div ref={mapContainer} style={{
          width: layout === 'split' ? '50%' : layout === 'map-only' ? '100%' : '0%',
          display: layout === 'list-only' ? 'none' : 'block',
          height: '100%',
          position: 'relative',
          transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        }} />

        {/* Floating Style Switcher (visible when map is shown) */}
        {layout !== 'list-only' && (
          <div style={{
            position: 'absolute', bottom: 24, right: 24,
            zIndex: 10, padding: '4px', borderRadius: '10px',
            background: 'rgba(9,13,22,0.9)',
            backdropFilter: 'blur(8px)',
            border: '1px solid rgba(99,102,241,0.25)',
            display: 'flex', gap: '4px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
          }}>
            {MAPBOX_STYLES.map(styleOption => (
              <button
                key={styleOption.name}
                type="button"
                onClick={() => setMapStyle(styleOption.url)}
                style={{
                  padding: '6px 10px',
                  borderRadius: '6px',
                  border: 'none',
                  background: mapStyle === styleOption.url ? '#6366f1' : 'transparent',
                  color: mapStyle === styleOption.url ? '#fff' : '#94a3b8',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'all 0.15s ease',
                }}
              >
                <span>{styleOption.icon}</span>
                {!isMobile && <span>{styleOption.name.split(' ')[1] || styleOption.name}</span>}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Mobile Floating Toggle Button */}
      {isMobile && (
        <button
          type="button"
          onClick={() => setLayout(l => l === 'map-only' ? 'list-only' : 'map-only')}
          style={{
            position: 'absolute',
            bottom: 24,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 30,
            padding: '12px 24px',
            borderRadius: '999px',
            background: '#6366f1',
            color: '#fff',
            fontWeight: 700,
            boxShadow: '0 6px 20px rgba(0,0,0,0.6)',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          {layout === 'map-only' ? '📋 Show List' : '🗺️ Show Map'}
        </button>
      )}

      {/* Loading overlay */}
      {(loading || error) && (
        <div style={{
          position: 'absolute', top: 90, left: '50%', transform: 'translateX(-50%)',
          zIndex: 20, padding: '8px 20px', borderRadius: '999px',
          background: error ? '#7f1d1d' : '#1e1b4b',
          color: error ? '#fca5a5' : '#e0e7ff',
          fontSize: '13px', fontWeight: 600,
          border: '1px solid rgba(99,102,241,0.2)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        }}>
          {loading ? '⏳ Updating list...' : `⚠️ ${error}`}
        </div>
      )}
    </div>
  );
};

export default MapSearch;
