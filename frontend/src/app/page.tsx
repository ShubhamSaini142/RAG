"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { CenteredSpinner } from "@/components/ui/spinner";

export default function Home() {
  const router = useRouter();
  const { loading, me } = useAuth();

  React.useEffect(() => {
    if (loading) return;
    router.replace(me ? "/chat" : "/login");
  }, [loading, me, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <CenteredSpinner label="Loading…" />
    </div>
  );
}
