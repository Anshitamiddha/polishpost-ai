import { Outlet } from "react-router-dom";
import WorkspaceProvider from "../../features/workspace/WorkspaceProvider";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

function AppLayout (){
    return(
        // The provider sits here, inside the protected routes, so the
        // workspace list is only fetched for a logged-in user.
        <WorkspaceProvider>
            <div className="app-layout">
                <Sidebar />
                <main className="main-area">
                    <Topbar />
                    <Outlet />
                </main>
            </div>
        </WorkspaceProvider>
    );
}

export default AppLayout;
