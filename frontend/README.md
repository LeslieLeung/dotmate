# Dotmate Configuration Frontend

A modern React-based web interface for managing dotmate configuration with live preview functionality.

## Features

- **Visual Configuration Editor**: Manage devices, schedules, and view parameters through an intuitive UI
- **Live Preview**: Generate and preview how your views will look on the device
- **Dynamic Forms**: Automatically generated forms based on view type schemas
- **Multi-Device Support**: Manage multiple devices and schedules in one place
- **Type-Safe**: Built with TypeScript for better development experience

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **shadcn/ui** for beautiful, accessible UI components
- **Tailwind CSS** for styling
- **Radix UI** for headless component primitives

## Prerequisites

- Node.js >= 18
- npm or yarn
- The dotmate backend API running on `http://localhost:8000`

## Installation

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Usage

### Starting the Backend

Before using the frontend, make sure the backend API is running:

```bash
# From the project root directory
cd ..
python backend/api.py
```

The backend API should be running on `http://localhost:8000`

### Using the Interface

1. **API Configuration**: Enter your Quote/0 API key at the top
2. **Device Management**:
   - Add devices using the "Add Device" button
   - Configure device name and device ID
   - Switch between devices using tabs

3. **Schedule Configuration**:
   - Add schedules to devices using "Add Schedule"
   - Select view type from the dropdown
   - Configure cron expression for scheduling
   - Fill in view-specific parameters

4. **Preview**:
   - After configuring a schedule, use the preview panel on the right
   - Click "Generate Preview" to see how the view will render
   - Previews are generated server-side using the same code as the actual device

5. **Save Configuration**:
   - Click "Save Configuration" to persist changes to `config.yaml`
   - The configuration is validated before saving

## Available View Types

The frontend dynamically loads available view types from the backend. Current types include:

- **work**: Work countdown timer with clock-in/clock-out times
- **text**: Custom text messages
- **code_status**: WakaTime coding statistics
- **image**: Binary image display
- **title_image**: Generated text-based images
- **umami_stats**: Umami analytics statistics
- **github_contributions**: GitHub contribution heatmap

## Development

### Project Structure

```
frontend/
├── src/
│   ├── api/              # API client
│   ├── components/       # React components
│   │   ├── ui/          # shadcn/ui components
│   │   ├── ConfigEditor.tsx
│   │   ├── ViewParamsForm.tsx
│   │   └── PreviewPanel.tsx
│   ├── lib/             # Utilities
│   ├── types/           # TypeScript types
│   ├── App.tsx          # Main app component
│   └── index.css        # Global styles
├── components.json      # shadcn/ui config
└── tailwind.config.js   # Tailwind config
```

### Building for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## Troubleshooting

### Backend Connection Issues

If you see connection errors:
1. Ensure the backend is running on `http://localhost:8000`
2. Check CORS settings in `backend/api.py`
3. Verify the API base URL in `src/api/client.ts`

### Preview Not Generating

If previews fail to generate:
1. Check that all required parameters are filled
2. Ensure external services (WakaTime, Umami, GitHub) credentials are valid
3. Check backend logs for error details

### Styling Issues

If styles aren't loading:
1. Ensure Tailwind CSS is properly configured
2. Check that `index.css` is imported in `main.tsx`
3. Verify PostCSS configuration

## Contributing

When adding new components:
1. Use shadcn/ui components from `src/components/ui/`
2. Follow TypeScript best practices
3. Maintain consistent styling with Tailwind CSS
4. Update types in `src/types/index.ts` as needed

## License

Same as the parent dotmate project.
