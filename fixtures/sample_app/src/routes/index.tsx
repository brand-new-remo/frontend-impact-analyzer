import UserListPage from "@/pages/users/UserListPage";
import UserDetailPage from "@/pages/users/UserDetailPage";

export const routes = [
  // 用户列表
  {
    path: "/users",
    element: <UserListPage />,
    meta: { title: "用户管理" },
    children: [
      // 用户详情
      {
        path: "detail",
        element: <UserDetailPage />,
        meta: { title: "用户详情" },
      },
    ],
  },
];
