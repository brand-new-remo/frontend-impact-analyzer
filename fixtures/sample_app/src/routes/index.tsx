import UserListPage from "@/pages/users/UserListPage";
import UserDetailPage from "@/pages/users/UserDetailPage";

export const routes = [
  {
    path: "/users",
    element: <UserListPage />,
    children: [
      {
        path: "detail",
        element: <UserDetailPage />,
      },
    ],
  },
];
