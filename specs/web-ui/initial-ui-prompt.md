
# GreyVie Health Tracking Web UI

Create a React-based web application using Vite, TypeScript, and Tailwind CSS for a comprehensive health tracking platform focused on blood glucose management with integrated meal discovery and e-commerce features. The UI should have a clean, modern, and professional design with whites and soft colors as the primary palette.

## Authentication & Landing Page

- **Landing Page**:
  - Simple, clean, and elegant design showcasing key benefits
  - Clear value proposition with subtle animations
  - Streamlined sign-up flow and prominent login button
  - Informative sections highlighting features without overwhelming

- **Authentication**:
  - User-friendly login form with email/password
  - Social login options (Google, Apple)
  - Secure password reset flow
  - Remember me functionality
  - Account creation with minimal required fields

## Core Health Tracking Features

### Meal Tracking
- **Manual Entry Form**:
  - Food name, portion size, and timestamp fields
  - Searchable ingredient selector with autocomplete
  - Nutrition facts panel showing:
    - Carbohydrates (total, fiber, sugar)
    - Protein, fat (saturated, unsaturated)
    - Calories, sodium, cholesterol
  - Option to save meals as favorites/templates

- **Photo Recognition**:
  - Camera integration with capture button
  - Upload option for existing photos
  - Preview of captured/uploaded image
  - Integration with food recognition service
  - Manual correction interface for recognized items
  - Confidence indicators for detected foods

### Glucose Monitoring
- **Dexcom Integration**:
  - OAuth2 authorization flow with Dexcom API
  - Clear connection status indicators
  - Data sync controls and status
  - Last sync timestamp display

- **Manual BG Entry**:
  - Simple form with numeric input
  - Timestamp selection (defaulting to current time)
  - Pre/post meal indicators
  - Notes field for context

- **BG Visualization**:
  - Interactive time-series chart with zoom/pan
  - Day/week/month/custom time range selectors
  - Color-coded ranges (low/normal/high)
  - Overlay meal and activity markers on timeline
  - Statistical summary (average, time in range, etc.)
  - Anomaly highlighting

### Activity Tracking
- **Manual Activity Logging**:
  - Activity type selector with common options:
    - Cardio: walking, running, cycling, swimming
    - Sports: tennis, basketball, soccer
    - Strength: weight lifting, bodyweight exercises
    - Flexibility: yoga, stretching
    - Other: hiking, dancing, gardening
  - Duration, intensity, and calorie estimation
  - Notes field for details

- **Fitness Tracker Integration**:
  - Connection interface for popular devices
  - Activity summary display
  - Steps, distance, active minutes visualization
  - Heart rate data (if available)
  - Sleep tracking summary (if available)

## Recipe & Meal Discovery

- **Recipe Browser**:
  - Searchable database of diabetes-friendly recipes
  - Advanced filtering by:
    - Carbohydrate content (low to high)
    - Protein content (high to low)
    - Calorie range
    - Meal type (breakfast, lunch, dinner, snack)
    - Dietary restrictions (gluten-free, vegetarian, etc.)
  - Visual recipe cards with key nutrition highlights
  - Estimated glucose impact indicators

- **Meal Recommendations**:
  - AI-powered suggestions based on glucose trends
  - Personalized meal plans aligned with health goals
  - Quick-add functionality to meal tracker
  - One-click shopping list generation

- **Favorite & Save**:
  - Ability to bookmark preferred recipes
  - Custom collections (weeknight dinners, post-workout, etc.)
  - Share functionality for recipes

## E-Commerce & Subscription

- **Subscription Management**:
  - Plan selection and comparison
  - Current plan details and benefits
  - Billing history and upcoming payments
  - Easy plan switching/upgrading
  - Cancellation process with feedback collection

- **Payment Processing**:
  - Stripe integration for secure payments
  - Credit/debit card management
  - Alternative payment methods
  - Invoice history and receipt generation

- **Health Store**:
  - Curated marketplace for health products
  - Categories including:
    - Workout equipment (weights, bands, mats)
    - Calisthenics equipment (bars, rings, straps)
    - Diabetes maintenance items (glucose tablets, testing supplies)
    - Fitness trackers and compatible devices
  - Product filtering by price, rating, and category
  - Detailed product pages with specifications and reviews
  - Cart and checkout flow
  - Order tracking and history
  - Wishlist functionality

## Design Guidelines
- Utilize whites and soft colors for a clean, medical-adjacent aesthetic
- Implement ample white space for readability and focus
- Use subtle shadows and rounded corners for depth
- Ensure high contrast for important data points and actions
- Apply consistent, minimal iconography throughout
- Design for both light and dark mode with appropriate soft color palettes

## Technical Requirements
- Use React with TypeScript for type safety
- Implement responsive design using Tailwind CSS
- Use Shadcn/UI components for consistent styling
- Create modular, reusable components
- Implement proper form validation and error handling
- Ensure accessibility compliance (WCAG 2.1 AA)
- Add comprehensive test coverage with Vitest
- Integrate Stripe Elements for secure payment collection
- Implement proper authentication and authorization for premium features

## User Experience Considerations
- Design intuitive navigation between tracking, discovery, and shopping features
- Create clear visualizations that highlight correlations
- Provide helpful onboarding for first-time users
- Include polished loading states and error handling
- Support offline capabilities for manual entries
- Ensure cross-device consistency in the user experience
- Design seamless transitions between free and premium features
