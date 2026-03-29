import { ReportsPage } from "@/pages";
import AdminHomePage from "@/pages/admin/AdminHomePage";
import UserDetailPage from "@/pages/admin/UserDetailPage";
import AdvancedSettingsPage from "@/pages/admin/AdvancedSettingsPage";

export const routes = [
  {
    path: "/reports",
    element: <ReportsPage />,
  },
  {
    path: "/admin",
    element: <AdminHomePage />,
    children: [
      {
        path: "users",
        children: [
          {
            path: "detail",
            element: <UserDetailPage />,
          },
        ],
      },
      {
        path: "settings",
        children: [
          {
            path: "advanced",
            element: <AdvancedSettingsPage />,
          },
        ],
      },
    ],
  },
];
