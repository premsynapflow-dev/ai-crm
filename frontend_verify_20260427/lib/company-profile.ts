export const COMPANY_SECTOR_OPTIONS = [
  {
    value: 'bank',
    label: 'Bank / Co-operative Bank / Small Finance Bank / Payment Bank',
  },
  {
    value: 'nbfc_hfc',
    label: 'NBFC / HFC',
  },
  {
    value: 'fintech_payments',
    label: 'Fintech / Payments / PPI / Payment Aggregator / Payment System Operator',
  },
  {
    value: 'other_rbi_regulated',
    label: 'Other RBI-regulated financial entity',
  },
  {
    value: 'not_rbi_regulated',
    label: 'Not RBI-regulated / Non-financial company',
  },
] as const

export type CompanySectorValue = (typeof COMPANY_SECTOR_OPTIONS)[number]['value']

const RBI_ELIGIBLE_VALUES = new Set<CompanySectorValue>([
  'bank',
  'nbfc_hfc',
  'fintech_payments',
  'other_rbi_regulated',
])

export function getCompanySectorLabel(value?: string | null): string {
  return COMPANY_SECTOR_OPTIONS.find((option) => option.value === value)?.label ?? 'Not specified'
}

export function isRbiEligibleCompany(value?: string | null, explicitFlag?: boolean | null): boolean {
  if (typeof explicitFlag === 'boolean') {
    return explicitFlag
  }

  return RBI_ELIGIBLE_VALUES.has((value ?? 'not_rbi_regulated') as CompanySectorValue)
}
