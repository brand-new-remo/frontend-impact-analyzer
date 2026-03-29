import SearchForm from "@/components/shared/SearchForm";
import { fetchUsers } from "@/services/userApi";

export default function UserListPage() {
  fetchUsers();

  return (
    <section>
      <h1>User List</h1>
      <SearchForm />
    </section>
  );
}
