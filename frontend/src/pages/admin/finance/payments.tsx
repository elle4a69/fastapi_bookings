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
  id: string;
  payment_id: string;
  transaction_date: string;
  client_name: string;
  invoice_number: string;
  amount: number;
  method: 'Stripe' | 'Cash' | 'PayPal';
  status: 'Succeeded' | 'Refunded' | 'Failed';
}

export function PaymentsPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchPayments = async () => {
    try {
      setLoading(true);
      const data = await apiClient.get<Payment[]>('/api/admin/finance/payments');
      setPayments(data || []);
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

  const handleRefund = async (paymentId: string) => {
    try {
      await apiClient.post(`/api/admin/finance/payments/${paymentId}/refund`);
      toast.success('Refund initiated successfully');
      fetchPayments();
    } catch (error) {
      toast.error('Failed to initiate refund');
      console.error(error);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Succeeded':
        return <Badge className="bg-green-500/10 text-green-500 hover:bg-green-500/20 border-green-500/20">Succeeded</Badge>;
      case 'Failed':
        return <Badge variant="destructive">Failed</Badge>;
      case 'Refunded':
        return <Badge variant="secondary">Refunded</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
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
                  <TableHead>Invoice #</TableHead>
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
                  payments.map((payment) => (
                    <TableRow key={payment.id}>
                      <TableCell className="font-medium text-xs font-mono">{payment.payment_id}</TableCell>
                      <TableCell>{new Date(payment.transaction_date).toLocaleString()}</TableCell>
                      <TableCell>{payment.client_name}</TableCell>
                      <TableCell>{payment.invoice_number}</TableCell>
                      <TableCell>${payment.amount.toFixed(2)}</TableCell>
                      <TableCell>{payment.method}</TableCell>
                      <TableCell>{getStatusBadge(payment.status)}</TableCell>
                      <TableCell className="text-right">
                        {payment.status === 'Succeeded' && (
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
                  ))
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
