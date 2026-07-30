import React, { useState, useEffect } from 'react';
import { fetchWithAuth } from '@/lib/apiClient';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, Monitor, Smartphone, Globe, Shield, ShieldAlert, XCircle, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';

interface Session {
  id: string;
  ip_address: string;
  user_agent: string;
  login_at: string;
  is_current: boolean;
}

const SecuritySettings = () => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const fetchSessions = async () => {
    try {
      const response = await fetchWithAuth('/v2/sessions');
      const data = await response.json();
      setSessions(data);
    } catch (error) {
      toast.error('Failed to load active sessions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  const revokeSession = async (id: string) => {
    setRevokingId(id);
    try {
      await fetchWithAuth(`/v2/sessions/${id}`, { method: 'DELETE' });
      toast.success('Session revoked successfully');
      setSessions(sessions.filter(s => s.id !== id));
    } catch (error) {
      toast.error('Failed to revoke session');
    } finally {
      setRevokingId(null);
    }
  };

  const getDeviceIcon = (ua: string) => {
    const lowerUA = ua.toLowerCase();
    if (lowerUA.includes('mobi') || lowerUA.includes('android') || lowerUA.includes('iphone')) {
      return <Smartphone className="h-5 w-5 text-blue-500" />;
    }
    return <Monitor className="h-5 w-5 text-slate-500" />;
  };

  const getDeviceName = (ua: string) => {
    if (ua.includes('Windows')) return 'Windows PC';
    if (ua.includes('Macintosh')) return 'MacBook';
    if (ua.includes('iPhone')) return 'iPhone';
    if (ua.includes('Android')) return 'Android Device';
    if (ua.includes('Linux')) return 'Linux System';
    return 'Unknown Device';
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="border-red-100 shadow-sm">
        <CardHeader className="bg-red-50/30">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-red-600" />
            <CardTitle>Account Security</CardTitle>
          </div>
          <CardDescription>
            Manage your active sessions and where you're logged in.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Active Sessions ({sessions.length})
            </h3>
            
            <div className="divide-y border rounded-lg overflow-hidden">
              {sessions.length === 0 ? (
                <div className="p-8 text-center text-slate-500 italic bg-slate-50/50">
                  No other active sessions found.
                </div>
              ) : (
                sessions.map((session) => (
                  <div key={session.id} className="p-4 flex items-center justify-between hover:bg-slate-50/50 transition-colors">
                    <div className="flex items-start gap-4">
                      <div className="p-2 bg-white border rounded-md shadow-sm">
                        {getDeviceIcon(session.user_agent)}
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-900">{getDeviceName(session.user_agent)}</span>
                          {session.is_current && (
                            <span className="text-[10px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">
                              Current
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-xs text-slate-500">
                          <span className="flex items-center gap-1">
                            <Globe className="h-3 w-3" />
                            {session.ip_address}
                          </span>
                          <span>•</span>
                          <span>Logged in {formatDistanceToNow(new Date(session.login_at))} ago</span>
                        </div>
                      </div>
                    </div>
                    
                    {!session.is_current && (
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="text-red-600 hover:text-red-700 hover:bg-red-50 font-semibold"
                        onClick={() => revokeSession(session.id)}
                        disabled={revokingId === session.id}
                      >
                        {revokingId === session.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <>
                            <XCircle className="h-4 w-4 mr-1" />
                            Revoke
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-amber-100 bg-amber-50/10">
        <CardContent className="pt-6">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-amber-100 rounded-full">
              <ShieldAlert className="h-6 w-6 text-amber-600" />
            </div>
            <div className="space-y-2">
              <h4 className="font-bold text-amber-900">Security Recommendation</h4>
              <p className="text-sm text-amber-800 leading-relaxed">
                We recommend enabling <strong>Two-Factor Authentication (2FA)</strong> to add an extra layer of security to your account.
              </p>
              <Button variant="outline" size="sm" className="mt-2 border-amber-200 text-amber-900 hover:bg-amber-100">
                Configure 2FA
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SecuritySettings;
