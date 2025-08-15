import React from 'react'
import { useEffect, useState } from 'react'
import { AppSidebar } from "@/components/app-sidebar"
// import { useUserContext } from '@/contexts/UserContext'
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
import {  RefreshCcw, Plus ,Loader2, Lock, Trash2, Download } from "lucide-react"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose } from "@/components/ui/dialog"
import { AudioWaveform, ChartNoAxesCombined, DollarSign, Map, ShieldAlert, ShoppingBasket, Wrench } from 'lucide-react';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"


import { AgentsSetup } from '@/components/agents-setup';
import { ModeToggle } from '@/components/mode-toggle'
import { LoginCard } from "@/components/login";


import ag from '@/assets/ag.png';

import { getAvatarSrc } from '@/components/agents-definition'


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

import { Agent, getTeamLogo, Team, useTeamsContext } from '@/contexts/TeamsContext';

export default function Agents() {
  const { teams, loading, reloadTeams } = useTeamsContext();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<Team>(teams[0]);
  // const [isCreatingTeam, setIsCreatingTeam] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamDescription, setNewTeamDescription] = useState("");
  const [selectedLogo, setSelectedLogo] = useState("Wrench");
  const [isAuthenticated, setIsAuthenticated] = useState(BASE_URL)
  const [isCreatingTeamLoading, setIsCreatingTeamLoading] = useState(false);
  // const { userInfo } = useUserContext();

  const createNewTeam = async () => {
    if (!newTeamName.trim()) return;
    
    setIsCreatingTeamLoading(true);
    try {
      // Generate a unique team ID
      const teamId = crypto.randomUUID();
      
      // Create team object
      const newTeam = {
        id: teamId,
        team_id: teamId,
        name: newTeamName.trim(),
        description: newTeamDescription.trim(),
        logo: selectedLogo,
        agents: [],
        plan: "Free",
        starting_tasks: []
      };
      
      // Make API call to create the team
      const response = await fetch(`${BASE_URL}/teams`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newTeam)
      });
      
      if (!response.ok) {
        throw new Error(`Error creating team: ${response.statusText}`);
      }
      
      // Reset form
      setNewTeamName("");
      setNewTeamDescription("");
      setSelectedLogo("Wrench");
      
      // Reload teams list
      await reloadTeams();
      
      console.log('Team created successfully:', newTeam.name);
    } catch (error) {
      console.error('Error creating team:', error);
      // TODO: Show error message to user
    } finally {
      setIsCreatingTeamLoading(false);
    }
  };

  useEffect(() => {
    // console.log("Teams in consumer:", teams);
    if (teams.length > 0 && !selectedTeam) {
      setSelectedTeam(teams[0]);
      setAgents(teams[0].agents);
    }
  }, [teams]);
    
  /// TODO: better login -> MS EntraID
  const handleLogin = (email: string, password: string) => {
    console.log('Logging in with:', email)
    if (password === ACTIVATION_CODE || ALLWAYS_LOGGED_IN) {
      setIsAuthenticated(true)
    } else {
      console.log('Invalid activation code')
    }
  }

  // const handleLogout = () => {
  //   setIsAuthenticated(false)
  // }

  const handleTeamSelect = (team: Team) => {
    setAgents(team.agents);
    setSelectedTeam(team);
    console.log('Selected team:', selectedTeam.name);
    console.log('Selected agents:', agents);
  }

  const deleteTeam = async (teamId: string) => {
    if (!window.confirm("Are you sure you want to delete this team?")) return;
    try {
      const response = await fetch(`${BASE_URL}/teams/${teamId}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error(`Error deleting team: ${response.statusText}`);
      }
      await reloadTeams();
    } catch (error) {
      console.error('Error deleting team:', error);
      // TODO: Show error message to user
      await reloadTeams();
    }
  };

  const downloadTeam = async (team: Team) => {
    try {
      const response = await fetch(`${BASE_URL}/teams/${team.team_id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        throw new Error(`Error downloading team: ${response.statusText}`);
      }
      const teamJson = await response.json();

      const blob = new Blob([JSON.stringify(teamJson, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const safeName = (team.name || team.team_id || 'team').replace(/[^a-z0-9-_]+/gi, '_');
      a.download = `${safeName}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading team:', error);
    }
  };

  if (loading) {
    return (
      <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
        <SidebarProvider defaultOpen={true}>
          <AppSidebar onTeamSelect={handleTeamSelect} />
          <SidebarInset>
            <div className="flex items-center justify-center h-40">
              <Loader2 className="h-8 w-8 animate-spin" />  Initialzing...
            </div>
          </SidebarInset>
        </SidebarProvider>
      </ThemeProvider>
    );
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
            {/* Chat Interface */}
            <Card className={`md:col-span-2 flex flex-col`}>
              <CardHeader>
                <CardTitle>Team Management</CardTitle>
              </CardHeader>
              <CardContent className="flex-1 h-96">
                {/* <Separator className="my-2 invisible" /> */}
                <Dialog>
                  <DialogTrigger asChild>
                    <Button size="sm" variant="default" className="">
                      <Plus className="h-4 w-4" />
                      Create new team
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-[80vw] max-h-[100vh]">
                    <DialogHeader>
                      <DialogTitle>Create new team</DialogTitle>
                      <DialogDescription>
                        Create a new team of agents to help with specific tasks.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                      <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="team_name" className="text-right">Team Name</Label>
                        <Input 
                          id="team_name" 
                          value={newTeamName}
                          onChange={(e) => setNewTeamName(e.target.value)}
                          className="col-span-3" 
                          placeholder="My Awesome Team" 
                        />
                      </div>
                      <div className="grid grid-cols-4 items-center gap-4">
                        <Label htmlFor="team_description" className="text-right">Description</Label>
                        <Textarea 
                          id="team_description" 
                          value={newTeamDescription}
                          onChange={(e) => setNewTeamDescription(e.target.value)}
                          className="col-span-3" 
                          placeholder="Describe the purpose of this team" 
                        />
                      </div>
                      <div className="grid grid-cols-4 items-center gap-4">
                        <Label className="text-right">Team Icon</Label>
                        <div className="col-span-3 grid grid-cols-7 gap-2">
                          {["Wrench", "Map", "AudioWaveform", "ChartNoAxesCombined", "DollarSign", "ShieldAlert", "ShoppingBasket"].map((logo) => (
                            <div 
                              key={logo}
                              className={`flex flex-col items-center p-2 border rounded-md cursor-pointer ${selectedLogo === logo ? 'border-primary bg-primary/10' : 'border-muted'}`}
                              onClick={() => setSelectedLogo(logo)}
                            >
                              <div className="flex size-8 items-center justify-center">
                                {logo === "Wrench" && <Wrench className="h-6 w-6" />}
                                {logo === "Map" && <Map className="h-6 w-6" />}
                                {logo === "AudioWaveform" && <AudioWaveform className="h-6 w-6" />}
                                {logo === "ChartNoAxesCombined" && <ChartNoAxesCombined className="h-6 w-6" />}
                                {logo === "DollarSign" && <DollarSign className="h-6 w-6" />}
                                {logo === "ShieldAlert" && <ShieldAlert className="h-6 w-6" />}
                                {logo === "ShoppingBasket" && <ShoppingBasket className="h-6 w-6" />}
                              </div>
                              <span className="text-xs mt-1">{logo}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                    <DialogFooter className="sm:justify-start">
                      <DialogClose asChild>
                        <Button type="button" variant="secondary">
                          Cancel
                        </Button>
                      </DialogClose>
                      <Button 
                        type="button" 
                        onClick={createNewTeam} 
                        disabled={!newTeamName.trim() || isCreatingTeamLoading}
                      >
                        {isCreatingTeamLoading ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Creating...
                          </>
                        ) : (
                          "Create Team"
                        )}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
                <Separator orientation="vertical" className="mr-2 h-4 invisible" />
                {/*
                 <Button variant="outline" size="sm">
                  <Download className="h-4 w-4" />
                  Download team specification
                </Button>
                <Separator orientation="vertical" className="mr-2 h-4 invisible" />
                <Button variant="destructive" size="sm">
                  <Delete className="h-4 w-4" />
                  Delete team
                </Button> */}
                <Separator orientation="vertical" className="mr-2 h-4 invisible" />
                <Button variant="default" size="sm" onClick={reloadTeams}>
                  <RefreshCcw className="h-4 w-4" />
                  Reload Teams
                </Button>
              </CardContent>
              <CardFooter className="flex space-x-2">
                
              </CardFooter>
            </Card>
          </div> 
          <Separator  />
          {/* Agents setup */}
          {teams.map((team) => (
            <div className="min-h-[100vh] flex-1 rounded-xl bg-muted/50 md:min-h-min">
              {/* Chat Interface */}
              <Card className={`md:col-span-2 flex flex-col`}>
                <CardHeader>
                  <CardTitle>
                      <div className="flex items-center">
                          {React.createElement(getTeamLogo(team))}
                          <Separator orientation="vertical" className="mr-2 h-4 invisible" />
                          {team.name}
                          <Separator orientation="vertical" className="mr-2 h-4 invisible" />
                          {team.protected && <Lock className="inline h-4 w-4 text-muted-foreground" />}
                          <Button
                            variant="outline"
                            size="icon"
                            className="ml-2"
                            onClick={() => deleteTeam(team.id)}
                            title="Delete team"
                            disabled={!!team.protected}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                          <Button
                            variant="outline"
                            size="icon"
                            className="ml-2"
                            onClick={() => downloadTeam(team)}
                            title="Download team"
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                      </div>
                  </CardTitle>
                  <Separator />
                  <div className="space-x-2 container">
                    <p className="text-sm text-muted-foreground inline">{team.description}</p>
                </div>
                </CardHeader>
                <CardContent className="flex-1 h-96">
                  
                  <AgentsSetup
                  team={team}
                  getAvatarSrc={getAvatarSrc}
                  isCollapsed={false}
                  showDetails={true}
                  />
                </CardContent>
                <CardFooter className="flex space-x-2">
           
                </CardFooter>
              </Card>
  
              
            </div> 
          ))}
          
       
        </div>
        {/* Footer */}
      <Footer />
      </SidebarInset>
    </SidebarProvider>
    )}
    </ThemeProvider>
  )
}
