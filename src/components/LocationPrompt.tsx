/**
 * Location Prompt Component
 * Intelligently prompts user for location sharing
 */

import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { MapPin, Shield, Navigation, X } from 'lucide-react';
import { LocationService } from '@/lib/locationService';
import { useAuth } from '@/context/AuthContext';

interface LocationPromptProps {
  open: boolean;
  onClose: () => void;
  reason?: 'login' | 'journey' | 'sos';
}

export const LocationPrompt: React.FC<LocationPromptProps> = ({ open, onClose, reason = 'login' }) => {
  const { token, updateUser, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const getReasonText = () => {
    switch (reason) {
      case 'journey':
        return 'Track your journey in real-time';
      case 'sos':
        return 'Enable emergency SOS features';
      default:
        return 'Get personalized route recommendations';
    }
  };

  const handleAllow = async () => {
    setError('');
    setLoading(true);

    try {
      // Request location permission
      const location = await LocationService.requestLocation();

      if (!location) {
        throw new Error('Failed to get location');
      }

      // Update server
      if (token) {
        const success = await LocationService.updateServerLocation(location);
        
        if (success) {
          // Update local user state
          if (user) {
            updateUser({ ...user, location_enabled: true });
          }

          // Save preference
          LocationService.saveLocationPreference(true);
          LocationService.markLocationPrompted();

          onClose();
        } else {
          throw new Error('Failed to save location');
        }
      }
    } catch (err: any) {
      if (err.code === 1) {
        // User denied permission
        setError('Location permission denied. You can enable it later in settings.');
        LocationService.saveLocationPreference(false);
        LocationService.markLocationPrompted();
        
        setTimeout(() => onClose(), 2000);
      } else if (err.code === 2) {
        setError('Location unavailable. Please check your device settings.');
      } else if (err.code === 3) {
        setError('Location request timed out. Please try again.');
      } else {
        setError(err.message || 'Failed to get location');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDeny = () => {
    LocationService.saveLocationPreference(false);
    LocationService.markLocationPrompted();
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold flex items-center gap-2">
            <MapPin className="h-6 w-6 text-blue-600" />
            Share Your Location
          </DialogTitle>
          <DialogDescription>
            {getReasonText()}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 my-6">
          {/* Benefits */}
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <div className="mt-1">
                <Navigation className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="font-medium text-sm">Real-Time Journey Tracking</p>
                <p className="text-xs text-muted-foreground">
                  Track your trip progress and get timely updates
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="mt-1">
                <Shield className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="font-medium text-sm">Emergency SOS</p>
                <p className="text-xs text-muted-foreground">
                  Quick access to help with automatic location sharing
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="mt-1">
                <MapPin className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="font-medium text-sm">Personalized Recommendations</p>
                <p className="text-xs text-muted-foreground">
                  Get route suggestions based on your location
                </p>
              </div>
            </div>
          </div>

          {/* Privacy Notice */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <Shield className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="text-xs text-blue-800">
                <p className="font-semibold mb-1">Your privacy matters</p>
                <p>
                  Your location is encrypted and only used to improve your experience. 
                  You can disable it anytime from settings.
                </p>
              </div>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md border border-red-200">
              {error}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={handleDeny}
              disabled={loading}
              className="flex-1"
            >
              <X className="mr-2 h-4 w-4" />
              Not Now
            </Button>
            <Button
              onClick={handleAllow}
              disabled={loading}
              className="flex-1"
            >
              {loading ? (
                <>
                  <div className="mr-2 h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Getting Location...
                </>
              ) : (
                <>
                  <MapPin className="mr-2 h-4 w-4" />
                  Allow Access
                </>
              )}
            </Button>
          </div>

          <p className="text-xs text-center text-muted-foreground">
            You can change this preference anytime in your profile settings
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
