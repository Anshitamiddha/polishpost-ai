import { useAuth } from "../auth/useAuth";
import "./dashboard.css";

function DashboardPage() {
  const { user } = useAuth();

  return (
    <div className="dashboard-page">
      <h1>Welcome back, {user.name}</h1>
      <p>Here's your account at a glance.</p>

      <section className="profile-card" aria-label="Your profile">
        <dl>
          <div>
            <dt>Name</dt>
            <dd>{user.name}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{user.email}</dd>
          </div>
          <div>
            <dt>Account ID</dt>
            <dd>{user.id}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}

export default DashboardPage;
