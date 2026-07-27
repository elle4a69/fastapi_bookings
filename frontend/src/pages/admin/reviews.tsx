import { useEffect, useState } from "react";
import { 
  Star,
  LayoutGrid,
  List as ListIcon
} from "lucide-react";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../../components/ui/card";
import { Switch } from "../../components/ui/switch";
import { Badge } from "../../components/ui/badge";
import { Skeleton } from "../../components/ui/skeleton";
import { apiClient } from "../../lib/api";

interface Review {
  id: number | string;
  rating: number;
  client_name?: string;
  client?: { name: string };
  service_info?: string;
  provider_info?: string;
  service?: { name: string };
  provider?: { name: string };
  comments: string;
  is_approved: boolean;
  created_at: string;
}

export default function ReviewsPage() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  useEffect(() => {
    fetchReviews();
  }, []);

  const fetchReviews = async () => {
    setIsLoading(true);
    try {
      const response: any = await apiClient.get('/api/admin/management-reviews');
      // Handle standard response format { data: [...] } or direct array
      if (response?.data) {
        setReviews(response.data);
      } else if (Array.isArray(response)) {
        setReviews(response);
      } else {
        setReviews([]);
      }
    } catch (error) {
      console.error("Failed to fetch reviews:", error);
      // Fallback mock data for visual development if API is not present yet
      setReviews([
        {
          id: 1,
          rating: 5,
          client_name: "Alice Smith",
          service_info: "Swedish Massage",
          provider_info: "Sarah Jenkins",
          comments: "Absolutely wonderful experience! Highly recommended.",
          is_approved: true,
          created_at: new Date().toISOString()
        },
        {
          id: 2,
          rating: 3,
          client_name: "Bob Jones",
          service_info: "Deep Tissue",
          provider_info: "David Ross",
          comments: "It was okay, but a bit too much pressure for my liking.",
          is_approved: false,
          created_at: new Date(Date.now() - 86400000).toISOString()
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleApproval = async (review: Review, newStatus: boolean) => {
    try {
      // Optimistic update
      setReviews(prev => prev.map(r => r.id === review.id ? { ...r, is_approved: newStatus } : r));
      
      await apiClient.put(`/api/admin/management-reviews/${review.id}`, {
        is_approved: newStatus
      });
      
    } catch (error) {
      console.error("Failed to update review:", error);
      // Revert optimistic update
      setReviews(prev => prev.map(r => r.id === review.id ? { ...r, is_approved: !newStatus } : r));
    }
  };

  const renderStars = (rating: number) => {
    return Array.from({ length: 5 }).map((_, i) => (
      <Star
        key={i}
        className={`w-4 h-4 ${i < rating ? "text-yellow-400 fill-current" : "text-slate-600"}`}
      />
    ));
  };

  const getClientName = (review: Review) => review.client_name || review.client?.name || "Unknown Client";
  const getServiceInfo = (review: Review) => review.service_info || review.service?.name || "Unknown Service";
  const getProviderInfo = (review: Review) => review.provider_info || review.provider?.name || "Unknown Provider";

  return (
    <div className="flex flex-col gap-6 p-6 h-full overflow-y-auto w-full max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Client Reviews</h1>
          <p className="text-muted-foreground mt-1">Manage and moderate reviews left by your clients.</p>
        </div>
        
        <div className="flex items-center gap-2 bg-slate-800/50 p-1 rounded-lg border border-slate-800">
          <Button 
            variant={viewMode === 'grid' ? 'secondary' : 'ghost'} 
            size="sm" 
            onClick={() => setViewMode('grid')}
            className="px-2"
          >
            <LayoutGrid className="w-4 h-4 mr-2" />
            Grid
          </Button>
          <Button 
            variant={viewMode === 'list' ? 'secondary' : 'ghost'} 
            size="sm" 
            onClick={() => setViewMode('list')}
            className="px-2"
          >
            <ListIcon className="w-4 h-4 mr-2" />
            List
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-4">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <Card key={i} className="bg-slate-900 border-slate-800">
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-1/3 mb-2" />
                <Skeleton className="h-3 w-1/2" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-20 w-full mb-4" />
                <Skeleton className="h-10 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : reviews.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 text-center border rounded-xl bg-slate-900/30 border-slate-800 mt-4 h-[400px]">
          <Star className="w-12 h-12 text-slate-700 mb-4" />
          <h3 className="text-xl font-semibold">No reviews found</h3>
          <p className="text-muted-foreground mt-2 max-w-md">
            There are currently no client reviews to manage.
          </p>
        </div>
      ) : (
        <div className={
          viewMode === 'grid' 
            ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-4" 
            : "flex flex-col gap-4 mt-4"
        }>
          {reviews.map(review => (
            <Card key={review.id} className={`bg-slate-900 border-slate-800 transition-all hover:border-slate-700 ${viewMode === 'list' ? 'flex flex-row items-stretch' : ''}`}>
              <div className={`${viewMode === 'list' ? 'flex-1 flex flex-col p-6' : 'p-0'}`}>
                {viewMode === 'grid' && (
                  <CardHeader className="pb-2">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-1">
                        {renderStars(review.rating)}
                      </div>
                      <Badge variant={review.is_approved ? "default" : "secondary"} className={review.is_approved ? "bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20" : "bg-slate-800 text-slate-400"}>
                        {review.is_approved ? "Approved" : "Pending"}
                      </Badge>
                    </div>
                    <CardTitle className="text-lg">{getClientName(review)}</CardTitle>
                    <CardDescription className="text-xs flex flex-col gap-1 mt-1">
                      <span>Service: <span className="text-slate-300 font-medium">{getServiceInfo(review)}</span></span>
                      <span>Provider: <span className="text-slate-300 font-medium">{getProviderInfo(review)}</span></span>
                    </CardDescription>
                  </CardHeader>
                )}
                
                {viewMode === 'list' && (
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        <CardTitle className="text-lg m-0">{getClientName(review)}</CardTitle>
                        <div className="flex items-center gap-1">
                          {renderStars(review.rating)}
                        </div>
                      </div>
                      <div className="text-sm text-muted-foreground flex gap-4">
                        <span>Service: <span className="text-slate-300 font-medium">{getServiceInfo(review)}</span></span>
                        <span>Provider: <span className="text-slate-300 font-medium">{getProviderInfo(review)}</span></span>
                      </div>
                    </div>
                    <Badge variant={review.is_approved ? "default" : "secondary"} className={review.is_approved ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" : "bg-slate-800 text-slate-400"}>
                      {review.is_approved ? "Approved" : "Pending"}
                    </Badge>
                  </div>
                )}
                
                <CardContent className={viewMode === 'list' ? "p-0" : "pb-4"}>
                  <div className="bg-slate-950 p-4 rounded-md border border-slate-800 text-sm leading-relaxed text-slate-300 italic">
                    "{review.comments}"
                  </div>
                  <div className="text-xs text-slate-500 mt-4 flex items-center">
                    Submitted: {new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: 'numeric' }).format(new Date(review.created_at))}
                  </div>
                </CardContent>
              </div>
              
              {viewMode === 'grid' && <div className="px-6 pb-2"><div className="h-px w-full bg-slate-800" /></div>}
              
              <div className={`${viewMode === 'list' ? 'w-64 border-l border-slate-800 p-6 flex flex-col justify-center gap-4 bg-slate-950/30' : 'p-6 pt-2'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-slate-200">Visibility</span>
                    <span className="text-xs text-slate-500">
                      {review.is_approved ? "Visible to public" : "Hidden from public"}
                    </span>
                  </div>
                  <Switch 
                    checked={review.is_approved} 
                    onCheckedChange={(checked) => handleToggleApproval(review, checked)}
                  />
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
