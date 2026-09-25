import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { MobilePageShell } from '@/components/ui/mobile-page-shell';
import { ResponsiveDataTable, type ColumnDef } from '@/components/ui/responsive-data-table';
import { Undo2, RefreshCw, Search } from 'lucide-react';
import { toast } from 'sonner';

interface Payment {
  id: number | string;
  payment_id?: string;
  transaction_date?: string;
  created_at?: string;
  client_name?: string;
  invoice_number?: string;
  booking_id?: number;
  amount: number;
  currency?: string;
  method?: string;
  status: string;
}

export function PaymentsPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const fetchPayments = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get<any>('/api/admin/payments');
      const list = Array.isArray(res) ? res : res?.data || [];
      setPayments(list);
    } catch (error) {
      toast.error('Failed to load payments');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPayments();
  }, []);

  const handleRefund = async (paymentId: number | string) => {
    try {
      await apiClient.put(`/api/admin/payments/${paymentId}`, {
        status: 'refunded'
      });
      toast.success('Payment marked as refunded');
      fetchPayments();
    } catch (error) {
      toast.error('Failed to update payment status');
      console.error(error);
    }
  };

  const getStatusBadge = (status: string) => {
    const s = (status || '').toLowerCase();
    switch (s) {
      case 'succeeded':
      case 'paid':
      case 'completed':
        return <Badge className="bg-green-500/10 text-green-600 hover:bg-green-500/20 border-green-500/20">Succeeded</Badge>;
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>;
      case 'refunded':
        return <Badge variant="secondary">Refunded</Badge>;
      default:
        return <Badge variant="outline">{status || 'Pending'}</Badge>;
    }
  };

  const filteredPayments = payments.filter((p) => {
    const payCode = p.payment_id || `PAY-${p.id}`;
    const clientName = p.client_name || (p.booking_id ? `Booking #${p.booking_id}` : 'Direct Client');
    const invNumber = p.invoice_number || (p.booking_id ? `INV-${p.booking_id}` : '');
    const matchesSearch =
      payCode.toLowerCase().includes(search.toLowerCase()) ||
      clientName.toLowerCase().includes(search.toLowerCase()) ||
      invNumber.toLowerCase().includes(search.toLowerCase());
    const matchesStatus =
      statusFilter === 'all' || (p.status || '').toLowerCase() === statusFilter.toLowerCase();
    return matchesSearch && matchesStatus;
  });

  const columns: ColumnDef<Payment>[] = [
    {
      id: 'payment_id',
      header: 'Payment ID',
      sortable: true,
      cell: (p) => (
        <span className="font-mono text-xs font-semibold text-primary">
          {p.payment_id || `PAY-${p.id}`}
        </span>
      ),
    },
    {
      id: 'date',
      header: 'Transaction Date',
      sortable: true,
      cell: (p) => {
        const txDate = p.transaction_date || p.created_at;
        return <span className="text-xs text-muted-foreground">{txDate ? new Date(txDate).toLocaleString() : '—'}</span>;
      },
    },
    {
      id: 'client_name',
      header: 'Client',
      sortable: true,
      cell: (p) => (
        <span className="font-medium text-foreground">
          {p.client_name || (p.booking_id ? `Booking #${p.booking_id}` : 'Direct Client')}
        </span>
      ),
    },
    {
      id: 'reference',
      header: 'Invoice / Ref',
      defaultHidden: true,
      cell: (p) => (
        <span className="text-xs text-muted-foreground">
          {p.invoice_number || (p.booking_id ? `INV-${p.booking_id}` : '—')}
        </span>
      ),
    },
    {
      id: 'amount',
      header: 'Amount',
      sortable: true,
      align: 'right',
      cell: (p) => <span className="font-bold text-foreground">${Number(p.amount || 0).toFixed(2)}</span>,
    },
    {
      id: 'method',
      header: 'Method',
      cell: (p) => <span className="text-xs text-muted-foreground">{p.method || 'Credit Card'}</span>,
    },
    {
      id: 'status',
      header: 'Status',
      cell: (p) => getStatusBadge(p.status),
    },
    {
      id: 'actions',
      header: 'Actions',
      align: 'right',
      hideable: false,
      cell: (p) => {
        const isSucceeded = ['succeeded', 'paid', 'completed'].includes((p.status || '').toLowerCase());
        if (!isSucceeded) return null;
        return (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleRefund(p.id)}
            className="h-9 min-h-[44px] text-xs text-orange-600 hover:text-orange-700 hover:bg-orange-50 touch-manipulation gap-1.5"
            title="Issue Refund"
          >
            <Undo2 className="h-4 w-4" />
            <span className="hidden sm:inline">Refund</span>
          </Button>
        );
      },
    },
  ];

  return (
    <MobilePageShell
      title="Payments"
      description="View transaction records, processor receipts, and manage refunds"
      actions={
        <Button
          onClick={fetchPayments}
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
              placeholder="Search by ID, client, or ref..."
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
              <SelectItem value="succeeded">Succeeded</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
              <SelectItem value="refunded">Refunded</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <ResponsiveDataTable
          data={filteredPayments}
          columns={columns}
          keyExtractor={(p) => p.id}
          isLoading={loading}
          defaultSort={{ key: 'date', direction: 'desc' }}
          renderMobileCard={(p) => {
            const txDate = p.transaction_date || p.created_at;
            const payCode = p.payment_id || `PAY-${p.id}`;
            const clientName = p.client_name || (p.booking_id ? `Booking #${p.booking_id}` : 'Direct Client');
            const isSucceeded = ['succeeded', 'paid', 'completed'].includes((p.status || '').toLowerCase());

            return (
              <div className="p-3.5 rounded-lg border bg-card text-card-foreground shadow-xs space-y-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-semibold text-primary">{payCode}</span>
                  {getStatusBadge(p.status)}
                </div>

                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-foreground text-sm truncate">{clientName}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {txDate ? new Date(txDate).toLocaleString() : '—'}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Method: {p.method || 'Credit Card'}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-bold text-foreground text-base">
                      ${Number(p.amount || 0).toFixed(2)}
                    </p>
                  </div>
                </div>

                {isSucceeded && (
                  <div className="flex justify-end pt-2 border-t">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleRefund(p.id)}
                      className="h-10 min-h-[44px] px-3 text-xs text-orange-600 hover:text-orange-700 hover:bg-orange-50 touch-manipulation gap-1.5"
                    >
                      <Undo2 className="h-4 w-4" />
                      <span>Issue Refund</span>
                    </Button>
                  </div>
                )}
              </div>
            );
          }}
        />
      </div>
    </MobilePageShell>
  );
}

export default PaymentsPage;
