import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

// Merge Tailwind class names / 合并条件样式并处理冲突
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

