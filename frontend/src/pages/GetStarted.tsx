import {useState } from 'react'
import { AppSidebar } from "@/components/app-sidebar"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar"
import { ThemeProvider } from "@/components/theme-provider"
import { ModeToggle } from '@/components/mode-toggle'
import { LoginCard } from "@/components/login";
import ag from '@/assets/ag.png';


// TODO: FUJ! How to get ENV vars from SWA?
// Define environment variables with default values
const BASE_URL = import.meta.env.VITE_BASE_URL || "local";
const ALLWAYS_LOGGED_IN =
  import.meta.env.VITE_ALLWAYS_LOGGED_IN === "true" ? true : false;
const ACTIVATION_CODE = import.meta.env.VITE_ACTIVATON_CODE || "0000";

// console.log('VITE_BASE_URL:', BASE_URL);
// console.log('VITE_ALLWAYS_LOGGED_IN:', ALLWAYS_LOGGED_IN);
// console.log('VITE_ACTIVATON_CODE:', ACTIVATION_CODE);

import { Footer } from '@/components/Footer'

import { Agent, Team, useTeamsContext } from '@/contexts/TeamsContext';
import { AlarmClock } from 'lucide-react'
import { Card, CardHeader,CardContent, CardFooter} from "@/components/ui/card"

export default function GetStarted() {
  const { teams} = useTeamsContext();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<Team>(teams[0]);
  const [isAuthenticated, setIsAuthenticated] = useState(BASE_URL)

  /// TODO: better login -> MS EntraID
  const handleLogin = (email: string, password: string) => {
    console.log('Logging in with:', email)
    if (password === ACTIVATION_CODE || ALLWAYS_LOGGED_IN) {
      setIsAuthenticated(true)
    } else {
      console.log('Invalid activation code')
    }
  }
  const handleTeamSelect = (team: Team) => {
    setAgents(team.agents);
    setSelectedTeam(team);
    console.log('Selected team:', selectedTeam.name);
    console.log('Selected agents:', agents);
  }
  return (
    <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
    {!isAuthenticated ? (
      <LoginCard handleLogin={handleLogin} />
    ) : (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar onTeamSelect={handleTeamSelect} />
      <SidebarInset>
        <header className="flex sticky top-0 bg-background h-14 shrink-0 items-center gap-2 border-b px-4 z-10 shadow">
          <div className="flex items-center gap-2 px-4 w-full">
            {/* <img src={banner} alt="Banner" className="h-64" /> */}
            {/* <SidebarTrigger />   */}
            {/* <Bot className="h-8 w-8" /> */}
            <img src={ag  } alt="Banner" className="h-8" />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden md:block">
                  <BreadcrumbLink href="#">
                    AutoGen & MagenticOne demo
                  </BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>Library</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
            <div className="ml-auto hidden items-center gap-2 md:flex">
        
   
            {/* <Separator orientation="vertical" className="mr-2 h-4" /> */}
            <ModeToggle />
            {/* <Separator orientation="vertical" className="mr-2 h-4" /> */}
            {/* {isAuthenticated ? (
              <Button variant="outline" onClick={handleLogout}>
                <LogOut />Log out
              </Button>
            ) : null} */}
                
            </div>
          </div>
        </header>
        {/* Main content */}
        <div className="flex flex-1 flex-col gap-4 p-4 pt-0">
            <div className="min-h-[100vh] flex-1 rounded-xl bg-muted/50 md:min-h-min">
            <Separator className="mb-4" />
        
            <Card className={`md:col-span-2 h-full flex flex-col`}>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <AlarmClock className="h-8 w-8" />
                    <div>
                      <h1 className="text-2xl font-semibold leading-tight">Get started</h1>
                      <p className="text-sm text-muted-foreground">Spin up the demo and explore multi‑agent features</p>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 space-y-6">
                  <section className="space-y-2">
                    <h2 className="text-lg font-semibold">What is this?</h2>
                    <p className="text-muted-foreground">
                      This app showcases AutoGen and MagenticOne teamwork. Use curated teams of agents to collaborate on tasks,
                      run conversations in the playground, and customize your own setups.
                    </p>
                  </section>

                  <section className="space-y-3">
                    <h3 className="text-base font-semibold">Quick start</h3>
                    <ol className="list-decimal pl-6 space-y-2 text-sm">
                      <li>
                        Go to <a href="/" className="underline underline-offset-4">Chat</a> (Playground) and send a message. The default team will collaborate to respond.
                      </li>
                      <li>
                        Explore predefined scenarios: many teams include <em>starting tasks</em> like “Research X” or “Draft Y”. Use them as prompts to see how agents coordinate.
                      </li>
                      <li>
                        Watch the conversation flow: roles will be delegated, tools may be invoked, and the final result will be synthesized.
                      </li>
                      <li>
                        Tweak your prompt and iterate. You can also attach context where supported (RAG/MCP agents), depending on the selected team.
                      </li>
                    </ol>
                  </section>

                  <section className="space-y-3">
                    <h3 className="text-base font-semibold">Advanced start</h3>
                    <ol className="list-decimal pl-6 space-y-2 text-sm">
                      <li>
                        Select a different <strong>Team of agents</strong> from the sidebar. Each team has unique skills, tools, and starting tasks.
                      </li>
                      <li>
                        Run a predefined <strong>use‑case scenario</strong> by choosing one of the team’s starting tasks as your initial prompt in Chat.
                      </li>
                      <li>
                        Or build your own: open <a href="/agents" className="underline underline-offset-4">Agents</a> to customize teams — add agents, define system messages, enable RAG/MCP capabilities, and set your own starting tasks.
                      </li>
                      <li>
                        Return to <a href="/" className="underline underline-offset-4">Chat</a> and test your customized team on your use case. Compare outputs across teams to see which collaboration works best.
                      </li>
                    </ol>
                  </section>

                  <section className="space-y-3">
                    <h3 className="text-base font-semibold">Explore the app</h3>
                    <ul className="list-disc pl-6 space-y-1 text-sm">
                      <li>
                        <a href="/" className="underline underline-offset-4">Playground</a> – chat with the currently selected team.
                      </li>
                      <li>
                        <a href="/agents" className="underline underline-offset-4">Agents</a> – browse and configure teams and agents.
                      </li>
                      <li>
                        <a href="/introduction" className="underline underline-offset-4">Introduction</a> – product overview and docs.
                      </li>
                    </ul>
                  </section>

                  <section className="space-y-2">
                    <h3 className="text-base font-semibold">Tips</h3>
                    <ul className="list-disc pl-6 space-y-1 text-sm text-muted-foreground">
                      <li>Use the theme toggle in the header to switch light/dark mode.</li>
                      <li>Team selection lives in the sidebar; it controls which agents you chat with.</li>
                      <li>Make sure your backend CORS allows the frontend origin when running locally.</li>
                    </ul>
                  </section>
                </CardContent>
            </Card>
       
            </div>
        </div>
        {/* Footer */}
      <Footer />
      </SidebarInset>
    </SidebarProvider>
    )}
    </ThemeProvider>
  );
}
