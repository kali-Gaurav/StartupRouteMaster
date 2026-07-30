/**
 * User Profile Card Component
 * Displays user information with edit button
 */

import { Users, Edit2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

interface UserProfileCardProps {
  user: {
    name: string;
    email: string;
    phone: string;
    created_at: string;
  } | null;
  isLoading: boolean;
  onEdit: () => void;
}

export function UserProfileCard({ user, isLoading, onEdit }: UserProfileCardProps) {
  if (isLoading) {
    return (
      <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
        <div className="space-y-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-40" />
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="bg-card border border-border rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-lg font-black flex items-center gap-2 uppercase tracking-tight">
          <Users className="w-5 h-5 text-primary" />
          Profile
        </h3>
        <button
          onClick={onEdit}
          className="p-2 hover:bg-muted rounded-lg transition-colors"
          title="Edit profile"
        >
          <Edit2 className="w-4 h-4 text-muted-foreground hover:text-foreground" />
        </button>
      </div>

      <div className="space-y-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">Name</p>
          <p className="text-lg font-black">{user.name || "Not set"}</p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">Email</p>
          <p className="text-sm font-medium break-all">{user.email}</p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">Phone</p>
          <p className="text-sm font-medium">{user.phone || "Not provided"}</p>
        </div>
        <div className="pt-4 border-t border-border">
          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">Member Since</p>
          <p className="text-sm font-medium">
            {user.created_at ? new Date(user.created_at).toLocaleDateString("en-IN", { dateStyle: 'long' }) : "—"}
          </p>
        </div>
      </div>
    </div>
  );
}

export default UserProfileCard;
