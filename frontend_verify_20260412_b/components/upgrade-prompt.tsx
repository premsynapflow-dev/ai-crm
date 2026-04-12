"use client"

import Link from 'next/link'
import { Lock, ArrowRight } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface UpgradePromptProps {
  title: string
  description: string
  requiredPlan: string
  compact?: boolean
}

export function UpgradePrompt({
  title,
  description,
  requiredPlan,
  compact = false,
}: UpgradePromptProps) {
  return (
    <Card className="border-amber-200 bg-gradient-to-br from-amber-50 via-white to-orange-50">
      <CardHeader className={compact ? 'pb-2' : 'pb-3'}>
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-amber-100 p-2 text-amber-700">
            <Lock className="h-4 w-4" />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CardTitle className={compact ? 'text-base' : 'text-lg'}>{title}</CardTitle>
              <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100">
                {requiredPlan}+ feature
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-3 pt-0">
        <p className="text-sm text-muted-foreground">
          Upgrade to unlock this workflow in SynapFlow.
        </p>
        <Button asChild size={compact ? 'sm' : 'default'}>
          <Link href="/pricing" className="gap-2">
            See Plans
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  )
}
