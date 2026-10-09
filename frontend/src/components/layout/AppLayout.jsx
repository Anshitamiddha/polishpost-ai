import Sidebar from "./Sidebar";
function Applayout (){
    return(
        <div className="app-layout">
            <Sidebar />
            <main className="main-content">
                <h1>Main Content</h1>
                <p>This is the main content area.</p>
            </main>
        </div>
    );
}

export default Applayout;