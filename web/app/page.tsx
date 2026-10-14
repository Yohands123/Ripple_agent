"use client";

import { useEffect, useState } from "react";
import { loadNetwork, type DataOrigin } from "@/lib/data";

export default function Home() {
  const [status, setStatus] = useState("Loading");

  useEffect(() => {
    loadNetwork().then((res) => {
      if (!res) setStatus("No network data found");
      else setStatus(`${res.data.nodes.length} nodes from ${res.origin satisfies DataOrigin}`);
    });
  }, []);

  return <main style={{ padding: 24 }}>{status}</main>;
}
