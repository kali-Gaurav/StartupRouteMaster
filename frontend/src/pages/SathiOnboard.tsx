import React, { useState } from 'react';
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { 
  Shield, 
  User, 
  Phone, 
  Mail, 
  MapPin, 
  FileText, 
  CheckCircle2, 
  ArrowRight, 
  ArrowLeft, 
  Award,
  Heart,
  Train,
  Zap
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useToast } from "@/components/ui/use-toast";

import { useAuth } from "@/context/AuthContext";
import { useNavigate } from "react-router-dom";
import { SathiKYC } from "@/components/SathiKYC";

const steps = [
  { id: 1, title: "Service Station", icon: <Train className="w-5 h-5" /> },
  { id: 2, title: "Identity Verification", icon: <Shield className="w-5 h-5" /> },
  { id: 3, title: "Training & Pulse", icon: <Zap className="w-5 h-5" /> },
];

export default function SathiOnboard() {
  const [currentStep, setCurrentStep] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { toast } = useToast();
  const { user, token } = useAuth();
  const navigate = useNavigate();
  
  const [formData, setFormData] = useState({
    fullName: '',
    phone: '',
    email: '',
    stations: '',
    specializations: [] as string[],
    aadharNumber: ''
  });

  const [sathiId, setSathiId] = useState<string | null>(null);
  const [isTracking, setIsTracking] = useState(false);

  const toggleTracking = () => {
    const { SathiManager } = require("@/lib/sathiManager");
    if (isTracking) {
      SathiManager.stopTracking();
      setIsTracking(false);
    } else {
      SathiManager.startTracking();
      setIsTracking(true);
      toast({
        title: "You are now Live!",
        description: "Travelers near your service stations can now see your active presence.",
      });
    }
  };

  React.useEffect(() => {
    const fetchExistingProfile = async () => {
      if (!user) return;
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/sathi/my-profile`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
          const data = await response.json();
          setSathiId(data.id);
          setFormData({
            fullName: data.full_name,
            phone: data.phone,
            email: data.email || '',
            stations: data.service_stations.join(', '),
            specializations: data.specializations,
            aadharNumber: '' // Don't fetch this back
          });
          // If already registered but not KYC complete, skip to KYC
          if (data.verification_status === 'pending') {
            setCurrentStep(2);
          } else if (data.verification_status !== 'none') {
            setCurrentStep(3);
          }
        }
      } catch (e) {
        console.error("No existing Sathi profile found");
      }
    };
    fetchExistingProfile();
  }, [user]);

  const nextStep = () => setCurrentStep(prev => Math.min(prev + 1, steps.length - 1));
  const prevStep = () => setCurrentStep(prev => Math.max(prev - 1, 0));

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

      if (currentStep === 2) {
        // Submit KYC
        const hashData = async (data: string) => {
          const encoder = new TextEncoder();
          const dataBuffer = encoder.encode(data);
          const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
          const hashArray = Array.from(new Uint8Array(hashBuffer));
          return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        };

        const encryptData = async (data: string) => {
          const encoder = new TextEncoder();
          const key = await crypto.subtle.generateKey(
            { name: "AES-GCM", length: 256 },
            true,
            ["encrypt", "decrypt"]
          );
          const iv = crypto.getRandomValues(new Uint8Array(12));
          const encrypted = await crypto.subtle.encrypt(
            { name: "AES-GCM", iv: iv },
            key,
            encoder.encode(data)
          );
          return {
            encryptedData: btoa(String.fromCharCode(...new Uint8Array(encrypted))),
            iv: btoa(String.fromCharCode(...iv))
          };
        };

        const aadharHash = await hashData(formData.aadharNumber);
        const { encryptedData, iv } = await encryptData(formData.aadharNumber);

        const kycPayload = {
          aadhar_hash: aadharHash,
          encrypted_aadhar: encryptedData,
          encryption_iv: iv,
          uidai_ref: "REF-" + Math.random().toString(36).substring(7).toUpperCase()
        };

        const response = await fetch(`${apiUrl}/api/sathi/kyc`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(kycPayload)
        });

        if (!response.ok) throw new Error("KYC Submission failed");
        
        toast({
          title: "Application Submitted!",
          description: "Our safety team will review your KYC documents within 24 hours.",
        });
        nextStep();
      } else {
        // Register or Update Profile
        const registerPayload = {
          full_name: formData.fullName,
          phone: formData.phone,
          email: formData.email,
          service_stations: formData.stations.split(',').map(s => s.trim()).filter(s => s),
          specializations: formData.specializations,
          age: 25, // Mock age
          gender: "Prefer not to say"
        };

        const response = await fetch(`${apiUrl}/api/sathi/register`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(registerPayload)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Registration failed");
        }
        
        const data = await response.json();
        setSathiId(data.id);
        nextStep();
      }
    } catch (e: any) {
      toast({
        title: "Submission Error",
        description: e.message,
        variant: "destructive"
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const specializations = [
    { id: 'women_safety', label: 'Women Safety', icon: <Shield className="w-4 h-4" /> },
    { id: 'elderly_care', label: 'Elderly Assistance', icon: <Heart className="w-4 h-4" /> },
    { id: 'family_travel', label: 'Family Guide', icon: <Award className="w-4 h-4" /> },
    { id: 'medical_first_aid', label: 'First Aid', icon: <Award className="w-4 h-4" /> },
  ];

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      
      <main className="flex-1 container mx-auto px-4 py-24 max-w-2xl">
        <div className="text-center mb-12">
           <div className="inline-flex p-3 bg-emerald-100 rounded-2xl mb-4">
              <Shield className="w-8 h-8 text-emerald-600" />
           </div>
           <h1 className="text-4xl font-black uppercase tracking-tighter italic">Join the Sathi Network</h1>
           <p className="text-muted-foreground mt-2">Become a verified safety companion and help travelers across India.</p>
        </div>

        {/* Stepper */}
        <div className="flex justify-between mb-12 relative">
           <div className="absolute top-1/2 left-0 w-full h-0.5 bg-muted -translate-y-1/2 z-0"></div>
           {steps.map((step, idx) => (
             <div key={step.id} className="relative z-10 flex flex-col items-center gap-2">
                <div className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center transition-all duration-500 border-2",
                  idx <= currentStep 
                    ? "bg-primary text-white border-primary shadow-[0_0_15px_rgba(var(--primary),0.3)]" 
                    : "bg-background text-muted-foreground border-muted"
                )}>
                   {idx < currentStep ? <CheckCircle2 className="w-6 h-6" /> : step.icon}
                </div>
                <span className={cn(
                  "text-[10px] font-black uppercase tracking-widest hidden md:block",
                  idx <= currentStep ? "text-foreground" : "text-muted-foreground"
                )}>
                  {step.title}
                </span>
             </div>
           ))}
        </div>

        <div className="bg-card border-2 border-border rounded-[2.5rem] p-8 md:p-12 shadow-2xl animate-in fade-in slide-in-from-bottom-4 duration-500">
           
           {currentStep === 0 && (
             <div className="space-y-6 animate-in fade-in duration-300">
                <h2 className="text-2xl font-bold mb-6">Personal Details</h2>
                <div className="space-y-4">
                   <div className="grid gap-2">
                      <label className="text-xs font-black uppercase tracking-widest opacity-60">Full Name (As per Aadhar)</label>
                      <div className="relative">
                         <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                         <input 
                           type="text" 
                           placeholder="John Doe" 
                           className="w-full pl-12 pr-4 py-4 bg-muted/50 rounded-2xl border-2 border-transparent focus:border-primary outline-none transition-all font-medium"
                           value={formData.fullName}
                           onChange={e => setFormData({...formData, fullName: e.target.value})}
                         />
                      </div>
                   </div>
                   <div className="grid gap-2">
                      <label className="text-xs font-black uppercase tracking-widest opacity-60">Aadhar Number</label>
                      <div className="relative">
                         <Shield className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                         <input 
                           type="text" 
                           placeholder="1234 5678 9012" 
                           className="w-full pl-12 pr-4 py-4 bg-muted/50 rounded-2xl border-2 border-transparent focus:border-primary outline-none transition-all font-medium"
                           value={formData.aadharNumber}
                           onChange={e => setFormData({...formData, aadharNumber: e.target.value})}
                         />
                      </div>
                   </div>
                   <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="grid gap-2">
                         <label className="text-xs font-black uppercase tracking-widest opacity-60">Phone Number</label>
                         <div className="relative">
                            <Phone className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <input 
                              type="tel" 
                              placeholder="+91 98765 43210" 
                              className="w-full pl-12 pr-4 py-4 bg-muted/50 rounded-2xl border-2 border-transparent focus:border-primary outline-none transition-all font-medium"
                              value={formData.phone}
                              onChange={e => setFormData({...formData, phone: e.target.value})}
                            />
                         </div>
                      </div>
                      <div className="grid gap-2">
                         <label className="text-xs font-black uppercase tracking-widest opacity-60">Email Address</label>
                         <div className="relative">
                            <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <input 
                              type="email" 
                              placeholder="john@example.com" 
                              className="w-full pl-12 pr-4 py-4 bg-muted/50 rounded-2xl border-2 border-transparent focus:border-primary outline-none transition-all font-medium"
                              value={formData.email}
                              onChange={e => setFormData({...formData, email: e.target.value})}
                            />
                         </div>
                      </div>
                   </div>
                </div>
             </div>
           )}

           {currentStep === 1 && (
             <div className="space-y-6 animate-in fade-in duration-300">
                <h2 className="text-2xl font-bold mb-6">Service & Specialization</h2>
                <div className="space-y-6">
                   <div className="grid gap-2">
                      <label className="text-xs font-black uppercase tracking-widest opacity-60">Preferred Stations (Codes, comma separated)</label>
                      <div className="relative">
                         <MapPin className="absolute left-4 top-4 w-4 h-4 text-muted-foreground" />
                         <textarea 
                           placeholder="NDLS, BCT, CNB..." 
                           className="w-full pl-12 pr-4 py-4 bg-muted/50 rounded-2xl border-2 border-transparent focus:border-primary outline-none transition-all font-medium h-32 resize-none"
                           value={formData.stations}
                           onChange={e => setFormData({...formData, stations: e.target.value})}
                         />
                      </div>
                   </div>
                   <div className="grid gap-3">
                      <label className="text-xs font-black uppercase tracking-widest opacity-60">Core Specializations</label>
                      <div className="grid grid-cols-2 gap-3">
                         {specializations.map(spec => (
                           <button
                             key={spec.id}
                             onClick={() => {
                               const exists = formData.specializations.includes(spec.id);
                               setFormData({
                                 ...formData,
                                 specializations: exists 
                                   ? formData.specializations.filter(s => s !== spec.id)
                                   : [...formData.specializations, spec.id]
                               });
                             }}
                             className={cn(
                               "flex items-center gap-3 p-4 rounded-2xl border-2 transition-all text-sm font-bold",
                               formData.specializations.includes(spec.id)
                                 ? "bg-primary/10 border-primary text-primary"
                                 : "bg-muted/50 border-transparent text-muted-foreground hover:bg-muted"
                             )}
                           >
                             {spec.icon}
                             {spec.label}
                           </button>
                         ))}
                      </div>
                   </div>
                </div>
             </div>
           )}

           {currentStep === 2 && sathiId && (
             <div className="animate-in fade-in duration-300">
                <SathiKYC 
                  sathiId={sathiId} 
                  onComplete={() => {
                    toast({
                      title: "KYC Verified!",
                      description: "Identity fingerprint recorded in Audit Ledger.",
                    });
                    nextStep();
                  }} 
                />
             </div>
           )}

           {currentStep === 3 && (
             <div className="text-center space-y-6 py-12 animate-in zoom-in duration-500">
                <div className="w-24 h-24 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-8">
                   <CheckCircle2 className="w-12 h-12 text-emerald-600" />
                </div>
                <h2 className="text-4xl font-black uppercase tracking-tighter italic">Application Submitted!</h2>
                <p className="text-lg text-muted-foreground max-w-md mx-auto leading-relaxed">
                   Thank you for stepping up, <span className="text-foreground font-bold">{formData.fullName}</span>. 
                   Our team is now verifying your credentials with the local authorities.
                </p>
                 <div className="pt-8 flex flex-col gap-3">
                    <div className="p-4 bg-muted/50 rounded-2xl flex items-center justify-between gap-4 text-left">
                       <div className="flex items-center gap-4">
                          <div className="p-2 bg-blue-100 rounded-lg">
                             <Award className="w-5 h-5 text-blue-600" />
                          </div>
                          <div>
                             <div className="text-xs font-black uppercase tracking-widest opacity-60">Status</div>
                             <div className="text-sm font-bold flex items-center gap-2">
                               {isTracking ? (
                                 <span className="text-emerald-600 flex items-center gap-1.5">
                                   <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                                   Active & Online
                                 </span>
                               ) : "Background Check Pending"}
                             </div>
                          </div>
                       </div>
                       
                       <button 
                         onClick={toggleTracking}
                         className={cn(
                           "px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all",
                           isTracking 
                             ? "bg-red-100 text-red-600 hover:bg-red-200" 
                             : "bg-emerald-600 text-white hover:bg-emerald-700 shadow-lg shadow-emerald-500/20"
                         )}
                       >
                         {isTracking ? "Go Offline" : "Go Online"}
                       </button>
                    </div>

                    <button 
                      onClick={() => window.location.href = '/dashboard'}
                      className="w-full py-4 bg-slate-900 text-white rounded-2xl font-black uppercase tracking-widest shadow-xl hover:scale-[1.02] active:scale-95 transition-all"
                    >
                      Go to Dashboard
                    </button>
                 </div>
             </div>
           )}

           {currentStep < 3 && (
             <div className="mt-12 flex items-center justify-between pt-8 border-t border-border">
                <button 
                  onClick={prevStep}
                  disabled={currentStep === 0}
                  className={cn(
                    "flex items-center gap-2 font-black uppercase tracking-widest text-xs transition-all",
                    currentStep === 0 ? "opacity-0 pointer-events-none" : "hover:text-primary"
                  )}
                >
                   <ArrowLeft className="w-4 h-4" /> Back
                </button>

                {currentStep < 2 ? (
                  <button 
                    onClick={nextStep}
                    className="px-8 py-4 bg-primary text-white rounded-2xl font-black uppercase tracking-widest shadow-lg shadow-primary/30 flex items-center gap-2 hover:scale-[1.02] active:scale-95 transition-all"
                  >
                     Next Step <ArrowRight className="w-4 h-4" />
                  </button>
                ) : (
                  <button 
                    onClick={handleSubmit}
                    disabled={isSubmitting}
                    className="px-10 py-4 bg-emerald-600 text-white rounded-2xl font-black uppercase tracking-widest shadow-lg shadow-emerald-500/30 flex items-center gap-2 hover:scale-[1.02] active:scale-95 transition-all disabled:opacity-50"
                  >
                     {isSubmitting ? (
                       <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                     ) : (
                       <>Submit Application <CheckCircle2 className="w-4 h-4" /></>
                     )}
                  </button>
                )}
             </div>
           )}
        </div>

        <div className="mt-12 p-8 border-2 border-border border-dashed rounded-3xl text-center">
           <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-2">Platform Integrity</p>
           <p className="text-[10px] text-muted-foreground/60 leading-relaxed max-w-sm mx-auto">
              All Sathi applications are subject to mandatory police verification and internal training. RouteMaster maintains a zero-tolerance policy for safety violations.
           </p>
        </div>
      </main>

      <Footer />
    </div>
  );
}
