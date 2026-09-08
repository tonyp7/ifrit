import {
  CircleUserRound,
  Languages as LanguagesIcon,
  LogOut,
  SunMoon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { canAccessNavItem, NAV_ITEMS } from "@/config/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { cn } from "@/lib/utils";
import type { ThemePreference } from "@/types/user";

// Single shared style for every nav bar icon button (screen icons + profile) — same
// resting/hover/active treatment for all of them. `aria-[current=page]` picks up the
// `aria-current="page"` that NavLink sets on the active route automatically for plain
// links; the Configuration menu trigger isn't a NavLink (it opens a dropdown instead
// of navigating directly), so it sets `aria-current` manually via `isActive` below to
// stay visually consistent with the rest.
const navIconClass =
  "flex h-10 w-10 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground aria-[current=page]:bg-secondary aria-[current=page]:text-foreground";

export function NavBar() {
  const { user, logout } = useAuth();
  const { themePreference, setThemePreference } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  // NAV_ITEMS' `label` is the English source string, used here as the translation
  // key — it's defined at module scope in config/navigation.ts, outside any
  // component, so it can't call useTranslation() itself.
  const { t } = useTranslation(["common"]);

  if (!user) return null;
  const currentUser = user;

  const items = NAV_ITEMS.filter((item) => canAccessNavItem(item, currentUser.roles));

  // A child gated by its own `requiredRoles` (e.g. Validation, project_manager-only)
  // may not be visible to every user who can see the parent item at all —
  // Configuration's children have no such gate and are always both visible, same as
  // before this concept existed.
  function visibleChildren(item: (typeof items)[number]) {
    return item.children?.filter(
      (child) => !child.requiredRoles || child.requiredRoles.some((role) => currentUser.roles.includes(role)),
    );
  }

  return (
    <TooltipProvider delayDuration={200}>
      <nav
        className={cn(
          "fixed inset-x-0 bottom-0 z-40 flex h-14 flex-row items-center justify-around border-t bg-card",
          "md:inset-y-0 md:left-0 md:right-auto md:h-full md:w-14 md:flex-col md:justify-start md:gap-2 md:border-r md:border-t-0 md:py-4",
        )}
      >
        {items.map((item) => {
          const children = visibleChildren(item);
          return children && children.length > 1 ? (
            <Tooltip key={item.to}>
              <DropdownMenu>
                <TooltipTrigger asChild>
                  <DropdownMenuTrigger
                    className={navIconClass}
                    aria-current={location.pathname.startsWith(item.to) ? "page" : undefined}
                  >
                    <item.icon className="h-5 w-5" aria-hidden="true" />
                    <span className="sr-only">{t(item.label)}</span>
                  </DropdownMenuTrigger>
                </TooltipTrigger>
                <DropdownMenuContent side="right" align="start">
                  {children.map((child) => (
                    <DropdownMenuItem key={child.to} onClick={() => navigate(child.to)}>
                      {t(child.label)}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              <TooltipContent side="right">{t(item.label)}</TooltipContent>
            </Tooltip>
          ) : (
            <Tooltip key={item.to}>
              <TooltipTrigger asChild>
                <NavLink to={item.to} end className={navIconClass}>
                  <item.icon className="h-5 w-5" aria-hidden="true" />
                  <span className="sr-only">{t(item.label)}</span>
                </NavLink>
              </TooltipTrigger>
              <TooltipContent side="right">{t(item.label)}</TooltipContent>
            </Tooltip>
          );
        })}

        <div className="md:mt-auto">
          <Tooltip>
            <DropdownMenu>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger className={navIconClass}>
                  <CircleUserRound className="h-5 w-5" aria-hidden="true" />
                  <span className="sr-only">{t("Profile")}</span>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <DropdownMenuContent side="right" align="end">
                <DropdownMenuGroup>
                  <DropdownMenuLabel>{t("Appearance")}</DropdownMenuLabel>
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger>
                      <SunMoon className="mr-2 h-4 w-4" aria-hidden="true" />
                      {t("Dark Mode")}
                    </DropdownMenuSubTrigger>
                    <DropdownMenuSubContent>
                      <DropdownMenuRadioGroup
                        value={themePreference}
                        onValueChange={(value) =>
                          void setThemePreference(value as ThemePreference)
                        }
                      >
                        <DropdownMenuRadioItem value="light">{t("Light")}</DropdownMenuRadioItem>
                        <DropdownMenuRadioItem value="dark">{t("Dark")}</DropdownMenuRadioItem>
                        <DropdownMenuRadioItem value="system">
                          {t("System")}
                        </DropdownMenuRadioItem>
                      </DropdownMenuRadioGroup>
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger>
                      <LanguagesIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                      {t("Languages")}
                    </DropdownMenuSubTrigger>
                    <DropdownMenuSubContent>
                      <DropdownMenuRadioGroup value="en">
                        <DropdownMenuRadioItem value="en">{t("English")}</DropdownMenuRadioItem>
                      </DropdownMenuRadioGroup>
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                </DropdownMenuGroup>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => void logout()}>
                  <LogOut className="mr-2 h-4 w-4" aria-hidden="true" />
                  {t("Sign Out")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <TooltipContent side="right">{t("Profile")}</TooltipContent>
          </Tooltip>
        </div>
      </nav>
    </TooltipProvider>
  );
}
