import React from "react";
import { ArrowRight, Menu, X } from "lucide-react";
export type Page = "home" | "visit" | "checks" | "report" | "history" | "settings" | "cleanup" | "reminders" | "inspection";
const Navigate = React.createContext<(page: Page) => void>(() => {});

// Inline Button Component
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "secondary" | "ghost" | "gradient";
  size?: "default" | "sm" | "lg";
  children: React.ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "default", size = "default", className = "", children, ...props }, ref) => {
    const baseStyles = "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50";
    
    const variants = {
      default: "bg-white text-black hover:bg-gray-100",
      secondary: "bg-gray-800 text-white hover:bg-gray-700",
      ghost: "hover:bg-gray-800/50 text-white",
      gradient: "bg-gradient-to-b from-white via-white/95 to-white/60 text-black hover:scale-105 active:scale-95"
    };
    
    const sizes = {
      default: "h-10 px-4 py-2 text-sm",
      sm: "h-10 px-5 text-sm",
      lg: "h-12 px-8 text-base"
    };
    
    return (
      <button
        ref={ref}
        className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";

// Navigation Component
const headerPages = [['history', 'Checkup history'], ['reminders', 'Reminders'], ['settings', 'Settings']] as const;
const Navigation = React.memo(({page}: {page: Page}) => {
  const navigate = React.useContext(Navigate);
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);

  return (
    <header className="fixed top-0 w-full z-50 border-b border-gray-800/50 bg-black/80 backdrop-blur-md">
      <nav className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <button onClick={() => navigate("home")} className="text-xl font-semibold text-white">CareWare</button>
          <div className="hidden md:flex items-center gap-2" aria-label="App pages">
            {headerPages.map(([target,label])=><Button key={target} data-header-page={target} aria-current={page===target?'page':undefined} variant={page===target?'default':'ghost'} size="sm" onClick={()=>navigate(target)}>{label}</Button>)}
          </div>
          <button
            type="button"
            className="md:hidden text-white"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </nav>

      {mobileMenuOpen && (
        <div className="md:hidden bg-black/95 backdrop-blur-md border-t border-gray-800/50 animate-[slideDown_0.3s_ease-out]">
          <div className="flex flex-col gap-2 px-6 py-4">
            {headerPages.map(([target,label])=><Button key={target} data-mobile-page={target} aria-current={page===target?'page':undefined} variant={page===target?'default':'ghost'} onClick={()=>{navigate(target);setMobileMenuOpen(false)}}>{label}</Button>)}
          </div>
        </div>
      )}
    </header>
  );
});

Navigation.displayName = "Navigation";

// Hero Component
const Hero = React.memo(({dashboard}: {dashboard: React.ReactNode}) => {
  const navigate = React.useContext(Navigate);
  return (
    <section
      className="relative min-h-screen flex flex-col items-center justify-start px-6 py-20 md:py-24"
      style={{
        animation: "fadeIn 0.6s ease-out"
      }}
    >
      <style>{`

        
        * {
          font-family: 'Poppins', sans-serif;
        }
        
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        @keyframes slideDown {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>

      <aside className="mb-8 inline-flex flex-wrap items-center justify-center gap-2 px-4 py-2 rounded-full border border-gray-700 bg-gray-800/50 backdrop-blur-sm max-w-full">
        <span className="text-xs text-center whitespace-nowrap" style={{ color: '#9ca3af' }}>
          Local PC care. Private by design.
        </span>
        <a
          href="#history" onClick={(event) => { event.preventDefault(); navigate("history"); }}
          className="flex items-center gap-1 text-xs hover:text-white transition-all active:scale-95 whitespace-nowrap"
          style={{ color: '#9ca3af' }}
          aria-label="View checkup history"
        >
          Checkup history
          <ArrowRight size={12} />
        </a>
      </aside>

      <h1
        className="text-4xl md:text-5xl lg:text-6xl font-medium text-center max-w-3xl px-6 leading-tight mb-6"
        style={{
          background: "linear-gradient(to bottom, #ffffff, #ffffff, rgba(255, 255, 255, 0.6))",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
          letterSpacing: "-0.05em"
        }}
      >
        Give your computer <br />the care it deserves
      </h1>

      <p className="text-sm md:text-base text-center max-w-2xl px-6 mb-10" style={{ color: '#9ca3af' }}>
        Check your PC, understand the results, and create a clear report.<br />Customer consent first. Everything stays on this computer.
      </p>

      <div className="flex items-center gap-4 relative z-10 mb-16">
        <Button
          type="button"
          variant="gradient"
          size="lg"
          className="rounded-lg flex items-center justify-center"
          aria-label="Start a CareWare checkup"
          onClick={() => navigate("visit")}
        >
          Get started
        </Button>
      </div>

      <div className="w-full max-w-5xl relative pb-20">
        <div
          className="absolute left-1/2 w-[90%] pointer-events-none z-0"
          style={{
            top: "-23%",
            transform: "translateX(-50%)"
          }}
          aria-hidden="true"
        >
          <img
            src="./assets/template-glow.png"
            alt=""
            className="w-full h-auto"
            loading="eager"
          />
        </div>
        
        <div className="relative z-10">
          {dashboard}
        </div>
      </div>
    </section>
  );
});

Hero.displayName = "Hero";

// Main Component
export default function Component({onNavigate, page, children, overlay, dashboard}: {page: Page; dashboard: React.ReactNode; onNavigate: (page: Page) => void; children?: React.ReactNode; overlay?: React.ReactNode}) {
  return (
    <Navigate.Provider value={onNavigate}><main className="min-h-screen bg-black text-white">
      <Navigation page={page} />
      {children || <Hero dashboard={dashboard} />}
      {overlay}
    </main></Navigate.Provider>
  );
}
