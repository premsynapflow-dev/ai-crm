"use client"

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Eye, EyeOff, Lock, Mail, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'

import { Logo } from '@/components/logo'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Spinner } from '@/components/ui/spinner'
import { authAPI } from '@/lib/api/auth'

export default function ForgotPasswordPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [otpSent, setOtpSent] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

  async function requestOtp(event: React.FormEvent) {
    event.preventDefault()
    setError('')

    if (!validEmail) {
      setError('Please enter a valid email')
      return
    }

    setIsLoading(true)
    try {
      await authAPI.forgotPassword({ email })
      setOtpSent(true)
      toast.success('OTP sent', {
        description: 'Check your email for the password reset code.',
      })
    } catch {
      toast.error('Could not send OTP', {
        description: 'Please try again later.',
      })
    } finally {
      setIsLoading(false)
    }
  }

  async function resetPassword(event: React.FormEvent) {
    event.preventDefault()
    setError('')

    if (!/^\d{6}$/.test(otp)) {
      setError('Enter the 6-digit OTP from your email')
      return
    }
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setIsLoading(true)
    try {
      await authAPI.resetPassword({
        email,
        otp,
        new_password: newPassword,
      })
      toast.success('Password updated', {
        description: 'You can now sign in with your new password.',
      })
      router.push('/login')
    } catch {
      setError('Invalid or expired OTP')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-purple-50 to-blue-50 p-4">
      <Card className="w-full max-w-md shadow-xl border-0">
        <CardHeader className="space-y-4 text-center pb-2">
          <div className="flex justify-center">
            <Logo size="lg" />
          </div>
          <div>
            <CardTitle className="text-2xl">Reset password</CardTitle>
            <CardDescription className="text-muted-foreground">
              {otpSent ? 'Enter the OTP from your email and choose a new password' : 'Get a one-time password sent to your email'}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={otpSent ? resetPassword : requestOtp} className="space-y-4">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="email">Email</FieldLabel>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="pl-10"
                    disabled={isLoading || otpSent}
                  />
                </div>
              </Field>

              {otpSent && (
                <>
                  <Field>
                    <FieldLabel htmlFor="otp">OTP</FieldLabel>
                    <div className="relative">
                      <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        id="otp"
                        inputMode="numeric"
                        maxLength={6}
                        placeholder="123456"
                        value={otp}
                        onChange={(event) => setOtp(event.target.value.replace(/\D/g, '').slice(0, 6))}
                        className="pl-10 tracking-[0.3em]"
                        disabled={isLoading}
                      />
                    </div>
                  </Field>

                  <Field>
                    <FieldLabel htmlFor="new-password">New password</FieldLabel>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        id="new-password"
                        type={showPassword ? 'text' : 'password'}
                        placeholder="Enter a new password"
                        value={newPassword}
                        onChange={(event) => setNewPassword(event.target.value)}
                        className="pl-10 pr-10"
                        disabled={isLoading}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                        tabIndex={-1}
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </Field>

                  <Field>
                    <FieldLabel htmlFor="confirm-password">Confirm password</FieldLabel>
                    <Input
                      id="confirm-password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="Confirm your new password"
                      value={confirmPassword}
                      onChange={(event) => setConfirmPassword(event.target.value)}
                      disabled={isLoading}
                    />
                  </Field>
                </>
              )}

              {error && <FieldError>{error}</FieldError>}
            </FieldGroup>

            <Button
              type="submit"
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Spinner className="mr-2" />
                  {otpSent ? 'Updating password...' : 'Sending OTP...'}
                </>
              ) : otpSent ? (
                'Change password'
              ) : (
                'Send OTP'
              )}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm text-muted-foreground">
            <Link href="/login" className="text-primary hover:underline font-medium">
              Back to sign in
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
