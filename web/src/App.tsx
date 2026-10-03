import { Moon, Search, Sun } from "lucide-react";
import { BrowserRouter, Link, Route, Routes, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Library } from "./pages/Library";
import { LessonPage } from "./pages/Lesson";
import { ThemeProvider, useTheme } from "./theme";

export function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <TopBar />
        <Routes>
          <Route path="/" element={<Library />} />
          <Route path="/lessons/:id/:tab?" element={<LessonPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

function TopBar() {
  const { theme, toggle } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const onLibrary = location.pathname === "/";

  // Searching from a lesson goes back to the Library, where the results are.
  const search = (q: string) => {
    const next = new URLSearchParams(onLibrary ? params : undefined);
    if (q) next.set("q", q);
    else next.delete("q");
    navigate({ pathname: "/", search: next.toString() }, { replace: onLibrary });
  };

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link to="/" className="brand">
          <img src="/synapto-mark.png" alt="" className="brand-mark" />
          <span>Synapto</span>
        </Link>
        <nav className="topnav">
          <Link to="/" className={onLibrary || location.pathname.startsWith("/lessons") ? "is-active" : undefined}>
            Lessons
          </Link>
        </nav>
        <div className="grow" />
        <label className="search">
          <Search size={16} strokeWidth={1.5} aria-hidden />
          <input
            aria-label="Search lessons"
            placeholder="Search lessons and concepts"
            value={onLibrary ? (params.get("q") ?? "") : ""}
            onChange={(e) => search(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="icon-btn"
          onClick={toggle}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
        >
          {theme === "dark" ? <Sun size={16} strokeWidth={1.5} /> : <Moon size={16} strokeWidth={1.5} />}
        </button>
      </div>
    </header>
  );
}

function NotFound() {
  return (
    <main className="page">
      <h1 className="h1">Page not found</h1>
      <p>
        <Link to="/">Back to all lessons</Link>
      </p>
    </main>
  );
}
