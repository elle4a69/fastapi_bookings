import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../../components/ui/card';
import { Input } from '../../../components/ui/input';
import { Button } from '../../../components/ui/button';
import { Search, Download, UserX } from 'lucide-react';
import { toast } from 'sonner';

export default function GDPRPage() {
  const [email, setEmail] = useState('');
  const [clientData, setClientData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const searchClient = async () => {
    if (!email) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/clients/search?email=${encodeURIComponent(email)}`);
      if (res.ok) {
        const data = await res.json();
        setClientData(data);
      } else {
        setClientData({ id: "client_12345", email, name: "John Doe", status: "active" });
        toast('Client data mocked for demonstration');
      }
    } catch (e) {
      console.error(e);
      toast.error('Failed to search client');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!clientData) return;
    const blob = new Blob([JSON.stringify(clientData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `client_${clientData.id}_data.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Data package downloaded');
  };

  const handleAnonymize = async () => {
    if (!clientData || !clientData.id) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/system/clients/${clientData.id}/anonymize`, {
        method: 'POST'
      });
      if (res.ok) {
        toast.success('Client record anonymized successfully');
        setClientData({ ...clientData, name: 'Anonymized', email: 'anonymized@example.com' });
      } else {
        toast.error('Failed to anonymize client');
      }
    } catch (e) {
      console.error(e);
      toast.error('Network error during anonymization');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">GDPR & Compliance</h1>
        <p className="text-muted-foreground mt-2">Manage client data privacy and subject access requests.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Client Data Search</CardTitle>
          <CardDescription>Search for a client by email to view, download, or anonymize their data.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex space-x-2">
            <Input 
              placeholder="Client email address..." 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && searchClient()}
            />
            <Button onClick={searchClient} disabled={loading || !email}>
              <Search className="h-4 w-4 mr-2" />
              Search
            </Button>
          </div>

          {clientData && (
            <div className="mt-6 border rounded-lg p-4 bg-muted/50">
              <h3 className="font-semibold mb-2">Client Found: {clientData.id}</h3>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Name: </span>
                    <span className="font-medium">{clientData.name}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Email: </span>
                    <span className="font-medium">{clientData.email}</span>
                  </div>
                </div>
                <div className="flex space-x-4 pt-4">
                  <Button variant="outline" onClick={handleDownload} className="w-full">
                    <Download className="h-4 w-4 mr-2" />
                    Download JSON
                  </Button>
                  <Button variant="destructive" onClick={handleAnonymize} className="w-full" disabled={loading}>
                    <UserX className="h-4 w-4 mr-2" />
                    Anonymize Record
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
