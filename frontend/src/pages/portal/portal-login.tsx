import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, ArrowRight, Sparkles, CheckCircle2, Lock, Smartphone, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { useClientPortal } from "@/context/client-portal-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const DEMO_CLIENTS = [
  { name: "Client 1 - Alice Walker", phone: "0411000001", role: "Regular Client" },
  { name: "Client 2 - Bob Taylor", phone: "0411000002", role: "Follow-up Client" },
  { name: "Client 3 - Charlie Evans", phone: "0411000003", role: "Wellness Client" },
];

export default function PortalLoginPage() {
  const navigate = useNavigate();
  const { sendOtp, verifyOtp, isAuthenticated, tenantSlug } = useClientPortal();

  const [identifier, setIdentifier] = useState("0411000001");
  const [otpCode, setOtpCode] = useState("");
  const [step, setStep] = useState<"phone" | "otp">("phone");
  const [isSending, setIsSending] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [receivedOtpHint, setReceivedOtpHint] = useState<string | null>(null);

  // Auto redirect if already signed in
  React.useEffect(() => {
    if (isAuthenticated) {
      navigate("/portal", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleSendOtp = async (targetPhoneOrEmail?: string) => {
    const target = targetPhoneOrEmail || identifier;
    if (!target.trim()) {
      toast.error("Please enter a mobile phone number or email.");
      return;
    }

    setIsSending(true);
    try {
      const res = await sendOtp(target);
      if (res.ok) {
        toast.success(`Verification code dispatched to ${target}!`);
        setReceivedOtpHint(res.active_code || res.demo_code || "123456");
        setOtpCode(res.demo_code || "123456"); // Pre-fill with demo code for seamless 1-click UX
        setStep("otp");
      } else {
        toast.error(res.message || "Could not send verification code.");
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to request verification code.");
    } finally {
      setIsSending(false);
    }
  };

  const handleVerifyOtp = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!otpCode.trim()) {
      toast.error("Please enter the 6-digit verification code.");
      return;
    }

    setIsVerifying(true);
    try {
      const res = await verifyOtp(identifier, otpCode);
      if (res.ok) {
        toast.success(`Welcome back, ${res.client?.name || "Client"}!`);
        navigate("/portal", { replace: true });
      } else {
        toast.error(res.error || "Invalid verification code.");
      }
    } catch (err: any) {
      toast.error(err.message || "Verification failed.");
    } finally {
      setIsVerifying(false);
    }
  };

  const handleQuickFill = (phone: string) => {
    setIdentifier(phone);
    handleSendOtp(phone);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-slate-100 to-slate-200 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 flex flex-col justify-center items-center p-4 sm:p-6">
      <div className="w-full max-w-md space-y-6">
        {/* Branding Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary/10 text-primary mb-2 shadow-sm border border-primary/20">
            <ShieldCheck className="w-7 h-7" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
            Client Portal
          </h1>
          <p className="text-sm text-muted-foreground">
            Access appointments, invoices, and resolve service queries for{" "}
            <span className="font-semibold text-foreground capitalize">{tenantSlug}</span>
          </p>
        </div>

        {/* Auth Card */}
        <Card className="border-border shadow-lg shadow-black/5 backdrop-blur-sm bg-card/95">
          <CardHeader className="space-y-1 pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-semibold">
                {step === "phone" ? "Sign In with Mobile or Email" : "Enter Verification Code"}
              </CardTitle>
              <Badge variant="outline" className="text-xs bg-muted/50">
                Passwordless OTP
              </Badge>
            </div>
            <CardDescription className="text-xs sm:text-sm">
              {step === "phone"
                ? "Enter your mobile phone or select a numbered demo client below."
                : `Enter the 6-digit code sent to ${identifier}`}
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            {step === "phone" ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendOtp();
                }}
                className="space-y-4"
              >
                <div className="space-y-2">
                  <Label htmlFor="identifier" className="text-xs font-medium">
                    Phone Number or Email Address
                  </Label>
                  <div className="relative">
                    <Smartphone className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="identifier"
                      type="text"
                      placeholder="e.g. 0411000001 or alice@example.com"
                      value={identifier}
                      onChange={(e) => setIdentifier(e.target.value)}
                      className="pl-9 text-sm"
                      required
                      autoFocus
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  className="w-full font-medium"
                  disabled={isSending}
                >
                  {isSending ? (
                    <>
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                      Dispatching Code...
                    </>
                  ) : (
                    <>
                      Send 6-Digit Code
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </>
                  )}
                </Button>
              </form>
            ) : (
              <form onSubmit={handleVerifyOtp} className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label htmlFor="otpCode" className="text-xs font-medium">
                      6-Digit Security Code
                    </Label>
                    <button
                      type="button"
                      onClick={() => setStep("phone")}
                      className="text-xs text-primary hover:underline"
                    >
                      Change Number
                    </button>
                  </div>
                  <div className="relative">
                    <Lock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="otpCode"
                      type="text"
                      maxLength={6}
                      placeholder="123456"
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                      className="pl-9 tracking-widest text-center text-lg font-mono"
                      required
                      autoFocus
                    />
                  </div>
                  {receivedOtpHint && (
                    <div className="rounded-md bg-amber-500/10 border border-amber-500/20 p-2.5 text-xs text-amber-700 dark:text-amber-300 flex items-center justify-between">
                      <span>
                        Demo Test Code: <strong>{receivedOtpHint}</strong> (or 123456)
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs"
                        onClick={() => setOtpCode(receivedOtpHint)}
                      >
                        Fill Code
                      </Button>
                    </div>
                  )}
                </div>

                <Button
                  type="submit"
                  className="w-full font-medium"
                  disabled={isVerifying}
                >
                  {isVerifying ? (
                    <>
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                      Verifying...
                    </>
                  ) : (
                    <>
                      Verify & Sign In
                      <CheckCircle2 className="w-4 h-4 ml-2" />
                    </>
                  )}
                </Button>
              </form>
            )}

            {/* 1-Click Quick Fill Demo Clients */}
            <div className="pt-3 border-t space-y-2">
              <div className="flex items-center gap-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <Sparkles className="w-3.5 h-3.5 text-primary" />
                1-Click Quick-Fill Demo Clients
              </div>
              <div className="grid grid-cols-1 gap-2">
                {DEMO_CLIENTS.map((c) => (
                  <button
                    key={c.phone}
                    type="button"
                    onClick={() => handleQuickFill(c.phone)}
                    className="w-full flex items-center justify-between p-2.5 text-left rounded-lg border border-border bg-background hover:bg-muted/60 transition-colors text-xs"
                  >
                    <div className="font-medium text-foreground">
                      {c.name}
                      <span className="block text-[11px] text-muted-foreground font-mono">
                        {c.phone}
                      </span>
                    </div>
                    <Badge variant="secondary" className="text-[10px] font-normal">
                      Quick Log In
                    </Badge>
                  </button>
                ))}
              </div>
            </div>
          </CardContent>

          <CardFooter className="flex justify-center border-t py-3 bg-muted/20">
            <p className="text-[11px] text-muted-foreground text-center">
              Secured with SMS/Email authentication token verification.
            </p>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
