import React, { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext'; // Assuming AuthContext provides token and checks admin role
import { fetchWithAuth } from '@/lib/apiClient'; // Reusable fetch function with auth
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle, CheckCircle2, Clock, X } from 'lucide-react'; // Icons for status
import { toast } from '@/components/ui/use-toast';

interface Transaction {
  id: string;
  amount: number;
  status: string;
  method: string;
  date: string;
  pnr?: string | null;
  is_refunded: boolean; // Assuming this might be relevant from user history
  refund_status?: string; // New field for refund status
  refund_id?: string | null;
  user_id: string; // Added for admin view
  type: string; // PAYMENT or REFUND
}

interface SystemStats {
  total_revenue: number;
  total_refunded: number;
  net_profit: number;
  timestamp: string;
}

const AdminFinancialDashboard: React.FC = () => {
  const { token, isAdmin } = useAuth(); // Assuming isAdmin check is available
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!token || !isAdmin) { // Ensure user is logged in and is an admin
        setError("Admin authentication required. Please log in as an administrator.");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);

        // Fetch System P&L Stats
        const statsResponse = await fetchWithAuth('/v2/ledger/system_pnl', {
          method: 'GET',
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!statsResponse.ok) throw new Error(`HTTP error! status: ${statsResponse.status}`);
        const statsData = await statsResponse.json();
        setSystemStats(statsData);

        // Fetch All Transactions for Admin view
        // Using /v2/ledger/stream for now, but ideally, an admin-specific endpoint would be better
        const historyResponse = await fetchWithAuth('/v2/ledger/stream?limit=50', { // Fetch more for admin view
          method: 'GET',
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!historyResponse.ok) throw new Error(`HTTP error! status: ${historyResponse.status}`);
        const historyData = await historyResponse.json();
        
        if (historyData.success) {
          setTransactions(historyData.ledger);
        } else {
          throw new Error(historyData.message || "Failed to fetch transaction history.");
        }

      } catch (err: any) {
        console.error("Error fetching admin dashboard data:", err);
        setError(err.message);
        toast({
          title: "Error Loading Dashboard",
          description: err.message,
          variant: "destructive",
        });
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [token, isAdmin]); // Reload if token or admin status changes

  if (loading) {
    return <div className="p-8 text-center">Loading Admin Dashboard...</div>;
  }

  if (error) {
    return <div className="p-8 text-center text-red-500">Error: {error}</div>;
  }

  if (!systemStats) {
    return <div className="p-8 text-center text-muted-foreground">No system stats available.</div>;
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-6">Admin Dashboard - Financial Overview</h1>
      
      {/* System Stats Card */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>System Financial Overview</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-grid-cols-3 gap-4">
          <div>
            <p className="text-sm text-muted-foreground">Total Revenue</p>
            <p className="text-2xl font-bold">₹{systemStats.total_revenue.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Total Refunded</p>
            <p className="text-2xl font-bold text-red-500">-₹{systemStats.total_refunded.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Net Profit</p>
            <p className={`text-2xl font-bold ${systemStats.net_profit >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {systemStats.net_profit >= 0 ? '+' : ''}₹{systemStats.net_profit.toFixed(2)}
            </p>
          </div>
        </CardContent>
        <div className="p-4 text-xs text-muted-foreground text-right">
          Last Updated: {new Date(systemStats.timestamp).toLocaleString()}
        </div>
      </Card>

      {/* Transactions Table */}
      <Card>
        <CardHeader>
          <CardTitle>All Transactions</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableCaption>All recent transactions across the platform.</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>User ID</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Details</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Refund Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transactions.map((tx) => (
                <TableRow key={tx.id}>
                  <TableCell className="font-medium">{new Date(tx.date).toLocaleString()}</TableCell>
                  <TableCell>{tx.user_id || 'N/A'}</TableCell>
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
                      <Badge variant="success">Paid</Badge>
                    ) : tx.status === 'pending' ? (
                      <Badge variant="outline">Pending</Badge>
                    ) : tx.is_refunded ? ( // This might be redundant if refund_status covers it
                      <Badge variant="destructive">Refunded</Badge>
                    ) : (
                      <Badge variant="destructive">Failed</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {tx.refund_status ? (
                      <Badge variant={
                        tx.refund_status === 'COMPLETED' ? 'secondary' : 
                        tx.refund_status === 'PROCESSING' ? 'outline' : 
                        tx.refund_status === 'PENDING' ? 'outline' : 
                        'destructive'
                      }>
                        {tx.refund_status.charAt(0).toUpperCase() + tx.refund_status.slice(1).toLowerCase()}
                      </Badge>
                    ) : (
                      <Badge variant="outline">N/A</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {/* Admin Actions for Refunds */}
                    {tx.status === 'completed' && tx.method === 'RAZORPAY' && !tx.is_refunded && tx.refund_status === 'REQUESTED' && (
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => handleRefundAction(tx.id, 'approve')}>Approve</Button>
                        <Button variant="destructive" size="sm" onClick={() => handleRefundAction(tx.id, 'reject')}>Reject</Button>
                      </div>
                    )}
                    {tx.refund_id && (tx.refund_status === 'PROCESSING' || tx.refund_status === 'PENDING') && (
                       <span className="text-sm text-muted-foreground">Ref ID: {tx.refund_id.substring(0, 6)}...</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
};

const handleRefundAction = async (refundId: string, action: 'approve' | 'reject') => {
  const endpoint = `/api/admin/refunds/${refundId}/${action}`;
  try {
    const response = await fetchWithAuth(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}` // Ensure token is included
      },
    });
    const data = await response.json();
    if (response.ok) {
      toast({
        title: `Refund ${action.charAt(0).toUpperCase() + action.slice(1)}d`,
        description: data.message,
      });
      // Re-fetch data to update the UI after action
      fetchData(); 
    } else {
      throw new Error(data.detail || `Failed to ${action} refund.`);
    }
  } catch (err: any) {
    console.error(`Error performing admin action on refund ${refundId}:`, err);
    toast({
      title: `Refund ${action === 'approve' ? 'Approval' : 'Rejection'} Failed`,
      description: err.message,
      variant: "destructive",
    });
  }
};

return (
  <div className="p-8">
    <h1 className="text-3xl font-bold mb-6">Admin Dashboard - Financial Overview</h1>

    {/* System Stats Card */}
    <Card className="mb-8">
      <CardHeader>
        <CardTitle>System Financial Overview</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <p className="text-sm text-muted-foreground">Total Revenue</p>
          <p className="text-2xl font-bold">₹{systemStats.total_revenue.toFixed(2)}</p>
        </div>
        <div>
          <p className="text-sm text-muted-foreground">Total Refunded</p>
          <p className="text-2xl font-bold text-red-500">-₹{systemStats.total_refunded.toFixed(2)}</p>
        </div>
        <div>
          <p className="text-sm text-muted-foreground">Net Profit</p>
          <p className={`text-2xl font-bold ${systemStats.net_profit >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {systemStats.net_profit >= 0 ? '+' : ''}₹{systemStats.net_profit.toFixed(2)}
          </p>
        </div>
      </CardContent>
      <div className="p-4 text-xs text-muted-foreground text-right">
        Last Updated: {new Date(systemStats.timestamp).toLocaleString()}
      </div>
    </Card>

    {/* Transactions Table */}
    <Card>
      <CardHeader>
        <CardTitle>All Transactions</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableCaption>All recent transactions across the platform.</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>User ID</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Details</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Refund Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {transactions.map((tx) => (
              <TableRow key={tx.id}>
                <TableCell className="font-medium">{new Date(tx.date).toLocaleString()}</TableCell>
                <TableCell>{tx.user_id || 'N/A'}</TableCell>
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
                    <Badge variant="success">Paid</Badge>
                  ) : tx.status === 'pending' ? (
                    <Badge variant="outline">Pending</Badge>
                  ) : tx.is_refunded ? ( // This might be redundant if refund_status covers it
                    <Badge variant="destructive">Refunded</Badge>
                  ) : (
                    <Badge variant="destructive">Failed</Badge>
                  )}
                </TableCell>
                <TableCell>
                  {tx.refund_status ? (
                    <Badge variant={
                      tx.refund_status === 'COMPLETED' ? 'secondary' : 
                      tx.refund_status === 'PROCESSING' ? 'outline' : 
                      tx.refund_status === 'PENDING' ? 'outline' : 
                      'destructive'
                    }>
                      {tx.refund_status.charAt(0).toUpperCase() + tx.refund_status.slice(1).toLowerCase()}
                    </Badge>
                  ) : (
                    <Badge variant="outline">N/A</Badge>
                  )}
                </TableCell>
                <TableCell>
                  {/* Admin Actions for Refunds */}
                  {tx.status === 'completed' && tx.method === 'RAZORPAY' && !tx.is_refunded && tx.refund_status === 'REQUESTED' && (
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={() => handleRefundAction(tx.id, 'approve')}>Approve</Button>
                      <Button variant="destructive" size="sm" onClick={() => handleRefundAction(tx.id, 'reject')}>Reject</Button>
                    </div>
                  )}
                  {tx.refund_id && (tx.refund_status === 'PROCESSING' || tx.refund_status === 'PENDING') && (
                     <span className="text-sm text-muted-foreground">Ref ID: {tx.refund_id.substring(0, 6)}...</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  </div>
);
};

const handleRefundAction = async (paymentId: string, action: 'approve' | 'reject') => {
// Placeholder for admin action API call
const endpoint = `/api/admin/refunds/${paymentId}/${action}`;
try {
  const response = await fetchWithAuth(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      // Token is automatically handled by fetchWithAuth
    },
    // Body might be needed for rejection reason, etc.
    body: JSON.stringify({ reason: action === 'reject' ? 'Admin rejected' : undefined }) 
  });
  const data = await response.json();
  if (response.ok) {
    toast({
      title: `Refund ${action.charAt(0).toUpperCase() + action.slice(1)}d`,
      description: data.message,
    });
    // Potentially re-fetch data or update UI optimistically
    // e.g., window.location.reload(); or update state directly
  } else {
    throw new Error(data.detail || `Failed to ${action} refund.`);
  }
} catch (err: any) {
  console.error(`Error performing admin action on refund ${paymentId}:`, err);
  toast({
    title: `Refund ${action === 'approve' ? 'Approval' : 'Rejection'} Failed`,
    description: err.message,
    variant: "destructive",
  });
}
};

export default AdminFinancialDashboard;

};

export default AdminFinancialDashboard;
