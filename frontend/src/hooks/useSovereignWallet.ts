import { useState, useCallback, useEffect } from "react";
import { claimIncentiveApi, getSovereignWalletApi, recordAbConversionApi } from "@/services/railwayBackApi";
import { useToast } from "@/components/ui/use-toast";
import { useAuth } from "@/context/AuthContext";

export interface SovereignCredit {
  id: string;
  amount: number;
  type: string;
  description: string;
  created_at: string;
  expires_at: string | null;
}

export interface SovereignWalletSummary {
  balance: number;
  bonus_balance: number;
  /**
   * Alias for compatibility with legacy code. Use bonus_balance instead.
   */
  bonus_credit_balance?: number;
  total_available: number;
  lifetime_earned: number;
  active_vouchers_count: number;
  credits: SovereignCredit[];
}

export function useSovereignWallet() {
  const [wallet, setWallet] = useState<SovereignWalletSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isClaiming, setIsClaiming] = useState(false);
  const { toast } = useToast();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const fetchWallet = useCallback(async () => {
    if (!isAuthenticated) {
      setWallet(null);
      return;
    }

    setIsLoading(true);
    try {
      const data = await getSovereignWalletApi();
      // Patch for legacy compatibility
      if (data && typeof data.bonus_balance === "number") {
        data.bonus_credit_balance = data.bonus_balance;
      }
      setWallet(data);
    } catch (error) {
      console.error("Failed to fetch Sovereign Wallet:", error);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  const claimIncentive = useCallback(async (amount: number, nudgeId: string, variant?: string, description?: string) => {
    setIsClaiming(true);
    try {
      const result = await claimIncentiveApi({
        amount,
        nudge_id: nudgeId,
        description
      });

      // Record A/B Conversion if variant is provided
      if (variant) {
        recordAbConversionApi({
          variant,
          goal: "conversion"
        }).catch(err => console.warn("Failed to record A/B conversion:", err));
      }
      
      // Update wallet immediately with the new balance
      if (wallet) {
        setWallet({
          ...wallet,
          bonus_balance: result.new_balance,
          total_available: wallet.balance + result.new_balance,
          lifetime_earned: wallet.lifetime_earned + amount,
        });
      } else {
        fetchWallet();
      }

      toast({
        title: "Incentive Claimed!",
        description: `₹${amount} has been added to your Sovereign Wallet.`,
      });
      
      return result;
    } catch (error) {
      console.error("Failed to claim incentive:", error);
      toast({
        title: "Claim Failed",
        description: "Could not process your incentive claim. Please try again later.",
        variant: "destructive"
      });
      throw error;
    } finally {
      setIsClaiming(false);
    }
  }, [wallet, fetchWallet, toast]);

  useEffect(() => {
    if (authLoading) return;
    fetchWallet();
  }, [fetchWallet, authLoading]);

  return {
    wallet,
    isLoading,
    isClaiming,
    fetchWallet,
    refreshWallet: fetchWallet,
    claimIncentive
  };
}
