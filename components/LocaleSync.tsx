"use client";

import { useEffect } from "react";
import { useAppState } from "@/lib/store";

export function LocaleSync() {
  const { locale } = useAppState();

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  return null;
}
