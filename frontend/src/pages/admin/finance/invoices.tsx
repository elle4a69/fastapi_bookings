import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Download, Mail, CreditCard, Search } from 'lucide-react';
import { toast } from 'sonner';

interface LineItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  total: number;
}

interface PaymentLog {
  id: string;
  date: string;
  amount: number;
  method: string;
}

interface Invoice {
  id: string;
  invoice_number: string;
  client_name: string;
  client_email?: string;
  billing_address?: string;
  issue_date: string;
  due_date: string;
  total: number;
  balance: number;
  status: 'Draft' | 'Sent' | 'Paid' | 'Void' | 'Overdue';
  line_items: LineItem[];
  payments: PaymentLog[];
}

export function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  useEffect(() => {
    fetchInvoices();
  }, []);

  const fetchInvoices = async () => {
    try {
      setLoading(true);
      const data = await apiClient.get<Invoice[]>('/api/admin/finance/invoices');
      setInvoices(data || []);
    } catch (error) {
      toast.error('Failed to load invoices');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleRowClick = (invoice: Invoice) => {
    setSelectedInvoice(invoice);
    setIsDrawerOpen(true);
  };

  const filteredInvoices = invoices.filter(inv => {
    const matchesSearch = inv.invoice_number.toLowerCase().includes(search.toLowerCase()) || 
                          inv.client_name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'all' || inv.status.toLowerCase() === statusFilter.toLowerCase();
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'paid': return <Badge className="bg-green-500/10 text-green-500 hover:bg-green-500/20 border-green-500/20">Paid</Badge>;
      case 'overdue': return <Badge variant="destructive">Overdue</Badge>;
      case 'draft': return <Badge variant="secondary">Draft</Badge>;
      case 'sent': return <Badge variant="outline" className="text-blue-500 border-blue-500/20 bg-blue-500/10">Sent</Badge>;
      case 'void': return <Badge variant="outline">Void</Badge>;
      default: return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold tracking-tight">Invoices</h1>
        <Button onClick={fetchInvoices}>Refresh</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Invoices</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex space-x-4 mb-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search invoices or clients..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="sent">Sent</SelectItem>
                <SelectItem value="paid">Paid</SelectItem>
                <SelectItem value="void">Void</SelectItem>
                <SelectItem value="overdue">Overdue</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Invoice #</TableHead>
                  <TableHead>Client</TableHead>
                  <TableHead>Issue Date</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Balance</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center h-24">Loading...</TableCell>
                  </TableRow>
                ) : filteredInvoices.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center h-24">No invoices found.</TableCell>
                  </TableRow>
                ) : (
                  filteredInvoices.map((inv) => (
                    <TableRow key={inv.id} className="cursor-pointer hover:bg-muted/50" onClick={() => handleRowClick(inv)}>
                      <TableCell className="font-medium">{inv.invoice_number}</TableCell>
                      <TableCell>{inv.client_name}</TableCell>
                      <TableCell>{new Date(inv.issue_date).toLocaleDateString()}</TableCell>
                      <TableCell>${inv.total.toFixed(2)}</TableCell>
                      <TableCell>${inv.balance.toFixed(2)}</TableCell>
                      <TableCell>{getStatusBadge(inv.status)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end space-x-2" onClick={(e) => e.stopPropagation()}>
                          <Button variant="ghost" size="icon" title="Pay">
                            <CreditCard className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Email">
                            <Mail className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Download PDF">
                            <Download className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Sheet open={isDrawerOpen} onOpenChange={setIsDrawerOpen}>
        <SheetContent className="w-[400px] sm:w-[540px] overflow-y-auto">
          {selectedInvoice && (
            <>
              <SheetHeader className="mb-6">
                <SheetTitle className="text-2xl">Invoice {selectedInvoice.invoice_number}</SheetTitle>
                <SheetDescription>
                  {getStatusBadge(selectedInvoice.status)}
                </SheetDescription>
              </SheetHeader>

              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground font-semibold mb-1">Billed To</p>
                    <p>{selectedInvoice.client_name}</p>
                    {selectedInvoice.client_email && <p className="text-muted-foreground">{selectedInvoice.client_email}</p>}
                    {selectedInvoice.billing_address && <p className="whitespace-pre-wrap mt-1">{selectedInvoice.billing_address}</p>}
                  </div>
                  <div className="text-right">
                    <p className="text-muted-foreground font-semibold mb-1">Details</p>
                    <p><span className="text-muted-foreground">Issued:</span> {new Date(selectedInvoice.issue_date).toLocaleDateString()}</p>
                    <p><span className="text-muted-foreground">Due:</span> {new Date(selectedInvoice.due_date).toLocaleDateString()}</p>
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold mb-3 border-b pb-2">Line Items</h4>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Description</TableHead>
                        <TableHead className="text-right">Qty</TableHead>
                        <TableHead className="text-right">Price</TableHead>
                        <TableHead className="text-right">Total</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selectedInvoice.line_items?.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell>{item.description}</TableCell>
                          <TableCell className="text-right">{item.quantity}</TableCell>
                          <TableCell className="text-right">${item.unit_price.toFixed(2)}</TableCell>
                          <TableCell className="text-right">${item.total.toFixed(2)}</TableCell>
                        </TableRow>
                      ))}
                      {!selectedInvoice.line_items?.length && (
                        <TableRow>
                          <TableCell colSpan={4} className="text-center text-muted-foreground py-4">No line items.</TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                  <div className="flex justify-end mt-4">
                    <div className="w-48 space-y-2 text-sm">
                      <div className="flex justify-between font-semibold text-lg border-t pt-2">
                        <span>Total:</span>
                        <span>${selectedInvoice.total.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between text-muted-foreground">
                        <span>Balance Due:</span>
                        <span>${selectedInvoice.balance.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {selectedInvoice.payments?.length > 0 && (
                  <div>
                    <h4 className="font-semibold mb-3 border-b pb-2">Payment Logs</h4>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Date</TableHead>
                          <TableHead>Method</TableHead>
                          <TableHead className="text-right">Amount</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {selectedInvoice.payments.map((payment) => (
                          <TableRow key={payment.id}>
                            <TableCell>{new Date(payment.date).toLocaleDateString()}</TableCell>
                            <TableCell>{payment.method}</TableCell>
                            <TableCell className="text-right">${payment.amount.toFixed(2)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

export default InvoicesPage;
