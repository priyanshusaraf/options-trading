import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
        // `chip` reproduces this cockpit's long-standing `.badge` look (see
        // index.css): 10px, uppercase, tight, square-ish. Stock shadcn badges are
        // 12px rounded-full sentence-case, which quietly rewrites the dense
        // trading-grid typography. Use `chip` for every status/toggle pill so a
        // re-skinned view stays visually identical to an un-migrated one; callers
        // pass their own accent via className (twMerge beats the base bg/text).
        chip: "border-transparent rounded text-[10px] uppercase tracking-wide px-1.5 font-semibold",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
