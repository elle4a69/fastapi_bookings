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
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Undo2 } from 'lucide-react';
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
        return <Badge className="bg-green-500/10 text-green-500 hover:bg-green-500/20 border-green-500/20">Succeeded</Badge>;
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>;
      case 'refunded':
        return <Badge variant="secondary">Refunded</Badge>;
      default:
        return <Badge variant="outline">{status || 'Pending'}</Badge>;
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold tracking-tight">Payments</h1>
        <Button onClick={fetchPayments}>Refresh</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Payment History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Payment ID</TableHead>
                  <TableHead>Transaction Date</TableHead>
                  <TableHead>Client Name</TableHead>
                  <TableHead>Invoice / Booking</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center h-24">Loading...</TableCell>
                  </TableRow>
                ) : payments.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center h-24">No payments found.</TableCell>
                  </TableRow>
                ) : (
                  payments.map((payment) => {
                    const txDate = payment.transaction_date || payment.created_at;
                    const formattedDate = txDate ? new Date(txDate).toLocaleString() : '—';
                    const payCode = payment.payment_id || `PAY-${payment.id}`;
                    const clientName = payment.client_name || (payment.booking_id ? `Booking #${payment.booking_id}` : 'Direct Client');
                    const invNumber = payment.invoice_number || (payment.booking_id ? `INV-${payment.booking_id}` : '—');
                    const method = payment.method || 'Credit Card';
                    const isSucceeded = ['succeeded', 'paid', 'completed'].includes((payment.status || '').toLowerCase());

                    return (
                      <TableRow key={payment.id}>
                        <TableCell className="font-medium text-xs font-mono">{payCode}</TableCell>
                        <TableCell>{formattedDate}</TableCell>
                        <TableCell>{clientName}</TableCell>
                        <TableCell>{invNumber}</TableCell>
                        <TableCell>${Number(payment.amount || 0).toFixed(2)}</TableCell>
                        <TableCell>{method}</TableCell>
                        <TableCell>{getStatusBadge(payment.status)}</TableCell>
                        <TableCell className="text-right">
                          {isSucceeded && (
                            <Button 
                              variant="ghost" 
                              size="sm" 
                              onClick={() => handleRefund(payment.id)}
                              className="text-orange-500 hover:text-orange-600 hover:bg-orange-50"
                              title="Issue Refund"
                            >
                              <Undo2 className="h-4 w-4 mr-2" />
                              Refund
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default PaymentsPage;
