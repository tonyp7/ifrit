import { Outlet } from "react-router-dom";

import { NavBar } from "@/components/NavBar";

export function AppLayout() {
  return (
    <div className="min-h-screen">
      <NavBar />
      <main className="min-h-screen pb-14 md:pb-0 md:pl-14">
        <Outlet />
      </main>
    </div>
  );
}
