import React, { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { fetchWithAuth } from '@/lib/apiClient';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { AlertTriangle, CheckCircle2, Clock } from 'lucide-react';
import { Separator } from '@/components/ui/separator';
import { toast } from '@/components/ui/use-toast';
import { Separator } from '@/components/ui/separator';


interface Transaction {
  id: string;
  amount: number;
  status: string;
  method: string;
  date: string;
  pnr?: string | null;
  is_refunded: boolean;
}

const PaymentHistory: React.FC = () => {
  const { user, token } = useAuth();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHistory = async () => {
      if (!user || !token) {
        setError("Authentication token not found. Please log in.");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const response = await fetchWithAuth('/v2/ledger/stream?limit=20', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          }
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (data.success) {
          setTransactions(data.ledger);
          // Assuming karma_balance is also relevant here
          // You might want to display it elsewhere or pass it down
        } else {
          throw new Error(data.message || "Failed to fetch transaction history.");
        }
      } catch (err: any) {
        console.error("Error fetching payment history:", err);
        setError(err.message);
        toast({
          title: "Error Fetching History",
          description: err.message,
          variant: "destructive",
        });
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [user, token]);

  if (loading) {
    return <div className="p-8 text-center">Loading transaction history...</div>;
  }

  if (error) {
    return <div className="p-8 text-center text-red-500">Error: {error}</div>;
  }

  if (transactions.length === 0) {
    return <div className="p-8 text-center text-muted-foreground">No transactions found. Make a payment to see your history.</div>;
  }

  return (
    <div className="p-8">
      <Card>
        <CardHeader>
          <CardTitle>Payment & Refund History</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableCaption>Your recent payment and refund transactions.</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Details</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transactions.map((tx) => (
                <TableRow key={tx.id}>
                  <TableCell className="font-medium">{new Date(tx.date).toLocaleString()}</TableCell>
                  <TableCell>{tx.type}</TableCell>
                  <TableCell>
                    {tx.pnr ? `PNR: ${tx.pnr}` : tx.method}
                    {tx.method && tx.method !== 'UPI' && ` (${tx.method})`}
                  </TableCell>
                  <TableCell className={tx.amount < 0 ? "text-red-500" : "text-green-500"}>
                    {tx.amount < 0 ? `-₹${Math.abs(tx.amount).toFixed(2)}` : `+₹${tx.amount.toFixed(2)}`}
                  </TableCell>
                  <TableCell>
                    {tx.status === 'completed' || tx.status === 'captured' ? (
                      <span className="flex items-center gap-1 text-green-500">
                        <CheckCircle2 className="h-4 w-4" /> Paid
                      </span>
                    {tx.is_refunded ? (
                        <span className="flex items-center gap-1 text-red-500">
                          <AlertTriangle className="h-4 w-4" /> Refunded
                        </span>
                      ) : tx.status === 'completed' || tx.status === 'captured' ? (
                        <span className="flex items-center gap-1 text-green-500">
                          <CheckCircle2 className="h-4 w-4" /> Paid
                        </span>
                      ) : tx.status === 'pending' ? (
                        <span className="flex items-center gap-1 text-yellow-500">
                          <Clock className="h-4 w-4" /> Pending
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-red-500">
                          <AlertTriangle className="h-4 w-4" /> Failed
                        </span>
                      )}
                    </TableCell>
                    {tx.status === 'completed' && tx.method === 'RAZORPAY' && !tx.is_refunded && ( // Only show button for completed Razorpay payments that haven't been refunded
                      <TableCell>
                        <Button variant="outline" size="sm" onClick={() => handleRequestRefund(tx.id)}>Request Refund</Button>
                      </TableCell>
                    )}
                    </TableRow>
                    ))}
                    </TableBody>
                    </Table>
                    </CardContent>
                    </Card>
                    </div>
                    );
                    };

                    const handleRequestRefund = async (paymentId: string) => {
                    try {
                    const response = await fetchWithAuth(`/payment/refund/${paymentId}`, {
                    method: 'POST',
                    headers: {
                    'Content-Type': 'application/json',
                    },
                    });
                    const data = await response.json();
                    if (response.ok) {
                    toast({
                    title: "Refund Requested",
                    description: data.message,
                    });
                    // Optionally re-fetch history or update UI optimistically
                    } else {
                    throw new Error(data.detail || "Failed to request refund.");
                    }
                    } catch (err: any) {
                    console.error("Error requesting refund:", err);
                    toast({
                    title: "Refund Request Failed",
                    description: err.message,
                    variant: "destructive",
                    });
                    }
                    };

                    export default PaymentHistory;

