import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { MobilePageShell } from '@/components/ui/mobile-page-shell';
import { ResponsiveDataTable, type ColumnDef } from '@/components/ui/responsive-data-table';
import { Download, Mail, CreditCard, Search, RefreshCw } from 'lucide-react';
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
      const res = await apiClient.get<any>('/api/admin/invoices');
      const list = Array.isArray(res) ? res : res?.data || [];
      const normalized: Invoice[] = list.map((inv: any) => ({
        id: String(inv.id),
        invoice_number: inv.invoice_number || `INV-${String(inv.id).padStart(4, '0')}`,
        client_name: inv.client_name || (inv.client?.name ? inv.client.name : `Client #${inv.client_id || '—'}`),
        issue_date: inv.issue_date || (inv.created_at ? inv.created_at.split('T')[0] : '—'),
        due_date: inv.due_date || (inv.created_at ? inv.created_at.split('T')[0] : '—'),
        total: Number(inv.total ?? inv.amount ?? 0),
        balance: Number((inv.total ?? inv.amount ?? 0) - (inv.amount_paid ?? 0)),
        status: inv.status ? (inv.status.charAt(0).toUpperCase() + inv.status.slice(1).toLowerCase()) as any : 'Draft',
        line_items: Array.isArray(inv.lines) ? inv.lines.map((l: any) => ({
          id: String(l.id),
          description: l.description,
          quantity: Number(l.quantity || 1),
          unit_price: Number(l.unit_price || 0),
          total: Number(l.amount || (l.quantity * l.unit_price) || 0),
        })) : [],
        payments: Array.isArray(inv.payments) ? inv.payments : [],
      }));
      setInvoices(normalized);
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
      case 'paid': return <Badge className="bg-green-500/10 text-green-600 hover:bg-green-500/20 border-green-500/20">Paid</Badge>;
      case 'overdue': return <Badge variant="destructive">Overdue</Badge>;
      case 'draft': return <Badge variant="secondary">Draft</Badge>;
      case 'sent': return <Badge variant="outline" className="text-blue-600 border-blue-500/20 bg-blue-500/10">Sent</Badge>;
      case 'void': return <Badge variant="outline">Void</Badge>;
      default: return <Badge variant="outline">{status}</Badge>;
    }
  };

  const columns: ColumnDef<Invoice>[] = [
    {
      id: 'invoice_number',
      header: 'Invoice #',
      accessorKey: 'invoice_number',
      sortable: true,
      cell: (inv) => <span className="font-semibold text-primary">{inv.invoice_number}</span>,
    },
    {
      id: 'client_name',
      header: 'Client',
      accessorKey: 'client_name',
      sortable: true,
      cell: (inv) => <span className="font-medium text-foreground">{inv.client_name}</span>,
    },
    {
      id: 'issue_date',
      header: 'Issue Date',
      accessorKey: 'issue_date',
      sortable: true,
      cell: (inv) => <span className="text-xs text-muted-foreground">{new Date(inv.issue_date).toLocaleDateString()}</span>,
    },
    {
      id: 'due_date',
      header: 'Due Date',
      accessorKey: 'due_date',
      sortable: true,
      defaultHidden: true,
      cell: (inv) => <span className="text-xs text-muted-foreground">{new Date(inv.due_date).toLocaleDateString()}</span>,
    },
    {
      id: 'total',
      header: 'Total',
      accessorKey: 'total',
      sortable: true,
      align: 'right',
      cell: (inv) => <span className="font-semibold">${inv.total.toFixed(2)}</span>,
    },
    {
      id: 'balance',
      header: 'Balance',
      accessorKey: 'balance',
      sortable: true,
      align: 'right',
      cell: (inv) => (
        <span className={inv.balance > 0 ? 'text-destructive font-medium' : 'text-muted-foreground'}>
          ${inv.balance.toFixed(2)}
        </span>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      cell: (inv) => getStatusBadge(inv.status),
    },
    {
      id: 'actions',
      header: 'Actions',
      align: 'right',
      hideable: false,
      cell: (inv) => (
        <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 min-h-[44px] min-w-[44px] touch-manipulation"
            title="Pay"
            onClick={() => toast.info(`Processing payment for ${inv.invoice_number}`)}
          >
            <CreditCard className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 min-h-[44px] min-w-[44px] touch-manipulation"
            title="Email"
            onClick={() => toast.success(`Email queued for ${inv.client_name}`)}
          >
            <Mail className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 min-h-[44px] min-w-[44px] touch-manipulation"
            title="Download PDF"
            onClick={() => toast.success(`Downloading PDF for ${inv.invoice_number}`)}
          >
            <Download className="h-4 w-4" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <MobilePageShell
      title="Invoices"
      description="Manage, track, and process billing invoices"
      actions={
        <Button
          onClick={fetchInvoices}
          variant="outline"
          className="h-10 min-h-[44px] w-full sm:w-auto gap-2 touch-manipulation"
        >
          <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
          <span>Refresh</span>
        </Button>
      }
    >
      <div className="space-y-4 min-w-0">
        <div className="flex flex-col sm:flex-row gap-2.5 sm:items-center justify-between">
          <div className="relative flex-1 max-w-full sm:max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            <Input
              placeholder="Search invoices or clients..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-10 min-h-[44px]"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full sm:w-[160px] h-10 min-h-[44px]">
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

        <ResponsiveDataTable
          data={filteredInvoices}
          columns={columns}
          keyExtractor={(inv) => inv.id}
          isLoading={loading}
          onRowClick={handleRowClick}
          defaultSort={{ key: 'issue_date', direction: 'desc' }}
          renderMobileCard={(inv) => (
            <div className="p-3.5 rounded-lg border bg-card text-card-foreground shadow-xs space-y-3 touch-manipulation active:bg-accent/40 transition-colors">
              <div className="flex items-center justify-between gap-2">
                <span className="font-bold text-base text-primary tracking-tight">
                  {inv.invoice_number}
                </span>
                {getStatusBadge(inv.status)}
              </div>

              <div className="flex items-start justify-between gap-2 text-sm">
                <div>
                  <p className="font-semibold text-foreground">{inv.client_name}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Issued: {new Date(inv.issue_date).toLocaleDateString()}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-foreground text-base">${inv.total.toFixed(2)}</p>
                  {inv.balance > 0 && (
                    <p className="text-xs text-destructive font-medium">
                      Due: ${inv.balance.toFixed(2)}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-end gap-1 border-t pt-2.5" onClick={(e) => e.stopPropagation()}>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-10 min-h-[44px] px-3 gap-1 text-xs touch-manipulation"
                  onClick={() => toast.info(`Processing payment for ${inv.invoice_number}`)}
                >
                  <CreditCard className="h-4 w-4 text-muted-foreground" />
                  <span>Pay</span>
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-10 min-h-[44px] px-3 gap-1 text-xs touch-manipulation"
                  onClick={() => toast.success(`Email queued for ${inv.client_name}`)}
                >
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <span>Email</span>
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-10 min-h-[44px] px-3 gap-1 text-xs touch-manipulation"
                  onClick={() => toast.success(`Downloading PDF for ${inv.invoice_number}`)}
                >
                  <Download className="h-4 w-4 text-muted-foreground" />
                  <span>PDF</span>
                </Button>
              </div>
            </div>
          )}
        />
      </div>

      <Sheet open={isDrawerOpen} onOpenChange={setIsDrawerOpen}>
        <SheetContent className="w-full sm:max-w-xl p-4 sm:p-6 overflow-y-auto pb-[calc(2rem+env(safe-area-inset-bottom))]">
          {selectedInvoice && (
            <>
              <SheetHeader className="mb-6 text-left">
                <div className="flex items-center justify-between pr-6">
                  <SheetTitle className="text-xl sm:text-2xl font-bold">
                    Invoice {selectedInvoice.invoice_number}
                  </SheetTitle>
                  {getStatusBadge(selectedInvoice.status)}
                </div>
                <SheetDescription className="text-xs sm:text-sm">
                  Full transaction breakdown and audit trail
                </SheetDescription>
              </SheetHeader>

              <div className="space-y-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm bg-muted/40 p-3.5 rounded-lg">
                  <div>
                    <p className="text-muted-foreground font-semibold text-xs mb-1 uppercase tracking-wider">Billed To</p>
                    <p className="font-medium text-foreground">{selectedInvoice.client_name}</p>
                    {selectedInvoice.client_email && <p className="text-xs text-muted-foreground mt-0.5">{selectedInvoice.client_email}</p>}
                    {selectedInvoice.billing_address && <p className="whitespace-pre-wrap text-xs text-muted-foreground mt-1">{selectedInvoice.billing_address}</p>}
                  </div>
                  <div className="sm:text-right border-t sm:border-t-0 pt-2 sm:pt-0">
                    <p className="text-muted-foreground font-semibold text-xs mb-1 uppercase tracking-wider">Details</p>
                    <p className="text-xs text-foreground"><span className="text-muted-foreground">Issued:</span> {new Date(selectedInvoice.issue_date).toLocaleDateString()}</p>
                    <p className="text-xs text-foreground mt-0.5"><span className="text-muted-foreground">Due:</span> {new Date(selectedInvoice.due_date).toLocaleDateString()}</p>
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold text-sm mb-3 border-b pb-2">Line Items</h4>
                  <div className="overflow-x-auto">
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
                            <TableCell className="font-medium text-xs sm:text-sm">{item.description}</TableCell>
                            <TableCell className="text-right text-xs sm:text-sm">{item.quantity}</TableCell>
                            <TableCell className="text-right text-xs sm:text-sm">${item.unit_price.toFixed(2)}</TableCell>
                            <TableCell className="text-right text-xs sm:text-sm font-semibold">${item.total.toFixed(2)}</TableCell>
                          </TableRow>
                        ))}
                        {!selectedInvoice.line_items?.length && (
                          <TableRow>
                            <TableCell colSpan={4} className="text-center text-muted-foreground py-4 text-xs">No line items.</TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>
                  <div className="flex justify-end mt-4">
                    <div className="w-full sm:w-56 space-y-2 text-sm bg-muted/30 p-3 rounded-lg">
                      <div className="flex justify-between font-bold text-base border-b pb-1.5">
                        <span>Total:</span>
                        <span>${selectedInvoice.total.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>Balance Due:</span>
                        <span className={selectedInvoice.balance > 0 ? 'text-destructive font-semibold' : ''}>
                          ${selectedInvoice.balance.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {selectedInvoice.payments?.length > 0 && (
                  <div>
                    <h4 className="font-semibold text-sm mb-3 border-b pb-2">Payment Logs</h4>
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
                            <TableCell className="text-xs">{new Date(payment.date).toLocaleDateString()}</TableCell>
                            <TableCell className="text-xs">{payment.method}</TableCell>
                            <TableCell className="text-right text-xs font-semibold">${payment.amount.toFixed(2)}</TableCell>
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
    </MobilePageShell>
  );
}

export default InvoicesPage;
