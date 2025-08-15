# Dream Team Frontend Documentation

## Overview

The Dream Team frontend is a modern React application built with Vite, TypeScript, and Tailwind CSS. It provides an intuitive interface for managing AI agent teams and facilitating multi-agent conversations.

## Architecture

### Core Technologies

- **React 18**: UI framework with hooks and context
- **TypeScript**: Type-safe JavaScript development
- **Vite**: Build tool and development server
- **Tailwind CSS**: Utility-first CSS framework
- **Shadcn/ui**: Component library built on Radix UI

### Key Libraries

- **React Router**: Client-side routing
- **Axios**: HTTP client for API communication
- **React Markdown**: Markdown rendering with syntax highlighting
- **Lucide React**: Icon library
- **React Context**: State management

## Project Structure

```
frontend/
├── src/
│   ├── components/         # Reusable UI components
│   │   ├── ui/            # Shadcn/ui components
│   │   ├── agents-setup.tsx
│   │   ├── app-sidebar.tsx
│   │   ├── markdown-display.tsx
│   │   └── mode-toggle.tsx
│   ├── contexts/          # React context providers
│   │   ├── TeamsContext.tsx
│   │   └── UserContext.tsx
│   ├── pages/             # Route components
│   │   ├── Playground.tsx
│   │   ├── Agents.tsx
│   │   ├── Introduction.tsx
│   │   └── GetStarted.tsx
│   ├── lib/               # Utility functions
│   ├── assets/            # Static assets
│   └── main.tsx           # Application entry point
├── public/                # Public assets
├── index.html             # HTML template
├── package.json           # Dependencies and scripts
├── tailwind.config.js     # Tailwind configuration
├── postcss.config.js      # PostCSS configuration
└── vite.config.ts         # Vite configuration
```

## Component Architecture

### Core Components

#### App Sidebar (`app-sidebar.tsx`)
- Navigation menu with collapsible sections
- Team selection interface
- Route-based active states

#### Agents Setup (`agents-setup.tsx`)
- Team and agent management interface
- Drag-and-drop functionality
- Modal dialogs for configuration

#### Markdown Display (`markdown-display.tsx`)
- Syntax-highlighted code blocks
- Copy-to-clipboard functionality
- Custom renderers for various content types

### UI Components (Shadcn/ui)

Located in `src/components/ui/`:
- **Button**: Multiple variants and sizes
- **Card**: Content containers with header/footer
- **Dialog**: Modal interfaces
- **Input/Textarea**: Form controls
- **Sidebar**: Collapsible navigation
- **Sheet**: Slide-out panels

## State Management

### Context Providers

#### TeamsContext
```typescript
interface Team {
  id: string;
  team_id: string;
  name: string;
  description: string;
  logo: string;
  agents: Agent[];
  starting_tasks: Task[];
  protected?: boolean;
}

interface Agent {
  name: string;
  description: string;
  system_message: string;
  icon: string;
  index_name?: string;
}
```

#### UserContext
```typescript
interface UserInfo {
  name: string;
  email: string;
  preferences: UserPreferences;
}
```

## Routing Structure

```
/                    # Playground (Chat Interface)
/playground-history  # Chat History
/agents             # Agent Team Management
/introduction       # Documentation
/get-started        # Getting Started Guide
/general            # Settings
```

## Styling System

### Tailwind Configuration

Custom theme extensions in `tailwind.config.js`:
- **CSS Variables**: Dark/light mode support
- **Animations**: Custom keyframes for loading states
- **Sidebar Colors**: Consistent navigation theming
- **Typography**: Responsive text sizing

### CSS Custom Properties

Defined in `src/index.css`:
```css
:root {
  --background: 0 0% 100%;
  --foreground: 240 10% 3.9%;
  --sidebar-background: 0 0% 98%;
  --sidebar-foreground: 240 5.3% 26.1%;
  /* ... additional properties */
}
```

## API Integration

### Environment Variables

```bash
# Backend API endpoint
VITE_BASE_URL=http://localhost:3100

# Authentication settings
VITE_ALLWAYS_LOGGED_IN=false
VITE_ACTIVATON_CODE=your_activation_code
```

### API Client

HTTP requests handled via Axios with:
- Base URL configuration
- Request/response interceptors
- Error handling middleware

## Features

### Chat Interface
- Real-time messaging with agent teams
- Markdown rendering with syntax highlighting
- Typing indicators and message history
- File upload for RAG integration

### Team Management
- Create and configure agent teams
- Add custom agents with specific capabilities
- Define starting tasks and prompts
- Import/export team configurations

### Agent Configuration
- System message customization
- Icon and description settings
- RAG agent creation with file upload
- MCP (Model Context Protocol) agent support

## Development Workflow

### Local Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Environment Setup

1. Copy environment template:
```bash
cp .env.example .env.local
```

2. Configure backend endpoint:
```bash
VITE_BASE_URL=http://localhost:3100
```

## Deployment

### Azure Static Web Apps

Configured for automatic deployment via GitHub Actions:
- Build artifact location: `dist/`
- API location: Not used (separate backend)
- App location: Root directory

### Build Configuration

Vite configuration in `vite.config.ts`:
```typescript
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    sourcemap: true
  },
  server: {
    port: 3000
  }
})
```

## Performance Optimizations

### Code Splitting
- Route-based lazy loading
- Component-level code splitting
- Dynamic imports for heavy libraries

### Bundle Optimization
- Tree shaking with ES modules
- Asset optimization with Vite
- CSS purging with Tailwind

### Caching Strategy
- Service worker for offline capability
- API response caching
- Static asset caching

## Accessibility Features

- **Keyboard Navigation**: Full keyboard support
- **Screen Reader**: ARIA labels and descriptions
- **Color Contrast**: WCAG compliant color schemes
- **Focus Management**: Proper focus handling in modals

## Testing Strategy

### Unit Testing
- Component testing with React Testing Library
- Utility function testing with Jest
- Context provider testing

### Integration Testing
- API integration tests
- User workflow testing
- Cross-browser compatibility

## Troubleshooting

### Common Issues

1. **Environment Variables**: Ensure `VITE_` prefix for client-side variables
2. **CORS**: Configure backend CORS for development
3. **Build Failures**: Check TypeScript compilation errors
4. **Hot Reload**: Restart dev server if not working

### Debug Tools

- React Developer Tools
- Vite development console
- Browser network inspection
- Redux DevTools (if using Redux)

## Browser Support

- **Modern Browsers**: Chrome 90+, Firefox 88+, Safari 14+
- **Mobile**: iOS Safari 14+, Chrome Mobile 90+
- **Progressive Enhancement**: Graceful degradation for older browsers