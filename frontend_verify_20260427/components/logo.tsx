import { cn } from '@/lib/utils'

interface LogoProps {
  className?: string
  showIcon?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export function Logo({ className, showIcon = true, size = 'md' }: LogoProps) {
  const sizes = {
    sm: { text: 'text-lg', icon: 'w-5 h-5' },
    md: { text: 'text-xl', icon: 'w-6 h-6' },
    lg: { text: 'text-2xl', icon: 'w-8 h-8' }
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      {showIcon && (
        <svg
          viewBox="0 0 32 32"
          fill="none"
          className={cn(sizes[size].icon)}
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#3B82F6" />
              <stop offset="100%" stopColor="#8B5CF6" />
            </linearGradient>
          </defs>
          {/* Neural network icon */}
          <circle cx="16" cy="8" r="3" fill="url(#logoGradient)" />
          <circle cx="8" cy="20" r="3" fill="url(#logoGradient)" />
          <circle cx="24" cy="20" r="3" fill="url(#logoGradient)" />
          <circle cx="16" cy="24" r="2" fill="url(#logoGradient)" />
          <path d="M16 11V22" stroke="url(#logoGradient)" strokeWidth="2" strokeLinecap="round" />
          <path d="M14 10L9 18" stroke="url(#logoGradient)" strokeWidth="2" strokeLinecap="round" />
          <path d="M18 10L23 18" stroke="url(#logoGradient)" strokeWidth="2" strokeLinecap="round" />
          <path d="M10 21L14 23" stroke="url(#logoGradient)" strokeWidth="1.5" strokeLinecap="round" />
          <path d="M22 21L18 23" stroke="url(#logoGradient)" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      )}
      <span className={cn(
        'font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent',
        sizes[size].text
      )}>
        SynapFlow
      </span>
    </div>
  )
}
