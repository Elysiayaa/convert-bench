"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DatabaseZap, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Convert", icon: Sparkles },
  { href: "/badcases", label: "Badcases", icon: DatabaseZap },
];

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b bg-background/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-3 font-semibold tracking-tight">
          <span className="grid size-9 place-items-center rounded-xl bg-primary text-primary-foreground">
            <Sparkles size={18} />
          </span>
          <span className="hidden sm:inline">ConvertBench</span>
        </Link>
        <nav className="flex items-center gap-1 rounded-xl border bg-card/70 p-1">
          {links.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground",
                  active && "bg-muted text-foreground shadow-sm",
                )}
              >
                <Icon size={16} />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
