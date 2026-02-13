import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import {
  ArrowLeft,
  User,
  Zap,
  Trophy,
  TrendingUp,
  Award,
  LogOut,
  Settings,
  Loader2,
  Link2,
  Check
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/hooks/use-toast";
import { getRailwayApiUrl } from "@/lib/utils";

interface UserProfile {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  email?: string;
  total_journeys: number;
  total_distance: number;
  favorite_route?: string;
  member_since: string;
  last_login: string;
  badges: Badge[];
  current_level: string;
  level_progress: number;
}

interface Badge {
  id: string;
  name: string;
  icon: string;
  earned_at: string;
  description: string;
}

const BADGES = {
  "beginner": { icon: "🎫", name: "Beginner", requirement: "1+ journeys" },
  "explorer": { icon: "🥉", name: "Explorer", requirement: "5+ journeys" },
  "regular": { icon: "🥈", name: "Regular Traveler", requirement: "10+ journeys" },
  "expert": { icon: "🥇", name: "Expert Traveler", requirement: "25+ journeys" },
  "master": { icon: "🏆", name: "Train Master", requirement: "50+ journeys" },
  "legend": { icon: "🌟", name: "Legend", requirement: "100+ journeys" }
};

const MiniAppProfile = () => {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [linkStatus, setLinkStatus] = useState<{ linked: boolean; linked_at?: string } | null>(null);
  const [linkCode, setLinkCode] = useState("");
  const [isLinking, setIsLinking] = useState(false);

  useEffect(() => {
    loadUserProfile();
    loadLinkStatus();
  }, []);

  const loadLinkStatus = async () => {
    const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    if (!userId) return;
    try {
      const res = await fetch(getRailwayApiUrl(`/api/telegram-link/status/${userId}`));
      if (res.ok) {
        const data = await res.json();
        setLinkStatus({ linked: data.linked, linked_at: data.linked_at });
      }
    } catch {
      setLinkStatus({ linked: false });
    }
  };

  const loadUserProfile = async () => {
    setIsLoading(true);
    try {
      const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
      if (!userId) return;

      const response = await fetch(getRailwayApiUrl(`/api/user/${userId}/profile`));
      if (response.ok) {
        const data = await response.json();
        setProfile(data);
      }
    } catch (error) {
      console.error("Failed to load profile:", error);
      toast({
        title: "Error",
        description: "Failed to load profile",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleLinkSubmit = async () => {
    const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    if (!userId || !linkCode.trim()) return;
    setIsLinking(true);
    try {
      const res = await fetch(getRailwayApiUrl("/api/telegram-link/link"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, code: linkCode.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        toast({ title: "Linked", description: "Telegram account linked." });
        setLinkCode("");
        loadLinkStatus();
      } else {
        toast({
          title: "Link failed",
          description: (data.detail as string) || "Invalid or expired code",
          variant: "destructive",
        });
      }
    } catch {
      toast({ title: "Error", description: "Could not link account", variant: "destructive" });
    } finally {
      setIsLinking(false);
    }
  };

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      const logoutData = {
        type: "LOGOUT",
        timestamp: new Date().toISOString()
      };

      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.sendData(JSON.stringify(logoutData));
        toast({
          title: "Logged Out",
          description: "You have been logged out successfully"
        });
        setTimeout(() => navigate("/"), 1500);
      }
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      setIsLoggingOut(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4 flex items-center justify-center">
        <Card className="shadow-lg">
          <CardContent className="p-8 flex flex-col items-center">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600 mb-4" />
            <p className="text-gray-600">Loading profile...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
        <div className="max-w-md mx-auto">
          <Card className="text-center py-12">
            <CardContent className="space-y-4">
              <div className="text-4xl">😕</div>
              <h3 className="text-lg font-bold text-gray-900">Profile Not Found</h3>
              <Button
                onClick={() => navigate("/mini-app/home")}
                className="w-full bg-blue-600 hover:bg-blue-700"
              >
                Return Home
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  const getLevelColor = (level: string) => {
    switch (level) {
      case "Beginner":
        return "bg-blue-100 text-blue-800";
      case "Regular":
        return "bg-purple-100 text-purple-800";
      case "Expert":
        return "bg-amber-100 text-amber-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-md mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center space-x-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/mini-app/home")}
            className="hover:bg-blue-200"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Profile</h1>
            <p className="text-sm text-gray-600">Your travel statistics</p>
          </div>
        </div>

        {/* User Info Card */}
        <Card className="shadow-lg border-0 overflow-hidden">
          <div className="bg-gradient-to-r from-blue-600 to-indigo-600 h-20" />
          <CardContent className="p-6 -mt-12 relative">
            <div className="bg-white rounded-full w-24 h-24 flex items-center justify-center border-4 border-white shadow-lg mx-auto mb-4">
              <User className="h-12 w-12 text-blue-600" />
            </div>

            <div className="text-center space-y-1">
              <h2 className="text-2xl font-bold text-gray-900">
                {profile.first_name} {profile.last_name || ""}
              </h2>
              {profile.username && (
                <p className="text-gray-600">@{profile.username}</p>
              )}
              <div className="flex justify-center gap-2 pt-2">
                <Badge className={`${getLevelColor(profile.current_level)}`}>
                  {profile.current_level}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-3">
          <Card>
            <CardContent className="p-4 text-center space-y-1">
              <TrendingUp className="h-6 w-6 text-blue-600 mx-auto" />
              <p className="text-2xl font-bold text-gray-900">{profile.total_journeys}</p>
              <p className="text-xs text-gray-600">Journeys</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center space-y-1">
              <Zap className="h-6 w-6 text-orange-600 mx-auto" />
              <p className="text-2xl font-bold text-gray-900">
                {(profile.total_distance / 1000).toFixed(0)}K
              </p>
              <p className="text-xs text-gray-600">km Traveled</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center space-y-1">
              <Trophy className="h-6 w-6 text-amber-600 mx-auto" />
              <p className="text-2xl font-bold text-gray-900">{profile.badges.length}</p>
              <p className="text-xs text-gray-600">Badges</p>
            </CardContent>
          </Card>
        </div>

        {/* Level Progress */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Level Progress</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="font-semibold text-gray-900">{profile.current_level}</p>
              <p className="text-sm text-gray-600">{profile.level_progress}%</p>
            </div>
            <Progress value={profile.level_progress} className="h-3" />
            <p className="text-xs text-gray-600">
              Keep journeying to reach the next level!
            </p>
          </CardContent>
        </Card>

        {/* Badges */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Award className="h-5 w-5 text-amber-600" />
              Achievements
            </CardTitle>
          </CardHeader>
          <CardContent>
            {profile.badges.length === 0 ? (
              <p className="text-sm text-gray-600 text-center py-4">
                Complete more journeys to unlock badges!
              </p>
            ) : (
              <div className="grid grid-cols-3 gap-3">
                {profile.badges.map((badge) => (
                  <div key={badge.id} className="text-center">
                    <div className="text-3xl mb-1">{badge.icon}</div>
                    <p className="text-xs font-semibold text-gray-900">{badge.name}</p>
                    <p className="text-xs text-gray-600 mt-1">
                      {new Date(badge.earned_at).toLocaleDateString()}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Link Telegram */}
        <Card className="border-2 border-dashed border-blue-200">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Link2 className="h-5 w-5 text-blue-600" />
              Link Telegram
            </CardTitle>
            <CardDescription>
              Link this account with the bot for notifications and personalization.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {linkStatus?.linked ? (
              <div className="flex items-center gap-2 text-green-700 bg-green-50 p-3 rounded-lg">
                <Check className="h-5 w-5 shrink-0" />
                <span className="text-sm font-medium">Telegram linked</span>
                {linkStatus.linked_at && (
                  <span className="text-xs text-gray-600">
                    since {new Date(linkStatus.linked_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            ) : (
              <>
                <p className="text-sm text-gray-600">
                  1. In Telegram, send <strong>/link</strong> to the bot.<br />
                  2. Enter the 6-digit code below.
                </p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="000000"
                    value={linkCode}
                    onChange={(e) => setLinkCode(e.currentTarget.value.replace(/\D/g, ""))}
                    className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-center font-mono text-lg"
                  />
                  <Button
                    onClick={handleLinkSubmit}
                    disabled={isLinking || linkCode.length !== 6}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    {isLinking ? <Loader2 className="h-5 w-5 animate-spin" /> : "Link"}
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Account Info */}
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="pt-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Member Since</span>
              <span className="font-semibold text-gray-900">
                {new Date(profile.member_since).toLocaleDateString()}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Last Login</span>
              <span className="font-semibold text-gray-900">
                {new Date(profile.last_login).toLocaleDateString()}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Action Buttons */}
        <div className="flex gap-3">
          <Button
            variant="outline"
            className="flex-1 border-2"
            onClick={() => navigate("/mini-app/home")}
          >
            <Settings className="h-4 w-4 mr-2" />
            Settings
          </Button>
          <Button
            variant="destructive"
            className="flex-1"
            onClick={handleLogout}
            disabled={isLoggingOut}
          >
            {isLoggingOut ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Logging out...
              </>
            ) : (
              <>
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default MiniAppProfile;