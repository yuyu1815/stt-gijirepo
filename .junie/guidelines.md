Project Development & AI Generation Prompt
AI Generation Directive
When generating code based on the following guidelines, all code comments and function descriptions (e.g., JSDoc) must be written in Japanese. The code itself (variable names, function names, etc.) must be in English.

1. Guiding Principles
   Clarity First: Prioritize writing code that others can understand in the shortest amount of time.

DRY Principle: Thoroughly apply the DRY (Don't Repeat Yourself) principle to avoid redundant logic.

2. Coding Conventions
   2.1. Naming
   Use specific and unambiguous names (e.g., fetch, download over get).

Names should be self-explanatory, indicating purpose or content.

Avoid generic names like tmp or retval.

Use positive boolean names (e.g., is_done, has_permission).

Maintain a consistent naming pattern across the entire codebase.

2.2. Structure
A function should do one thing and do it well.

Keep nesting levels shallow and use early returns for better readability.

Break down large expressions or complex conditions using explanatory variables.

Minimize the scope of variables and write to them only once if possible.

2.3. Comments
Comments should explain "why," not "what." Describe the purpose and background.

Add a brief explanation before complex algorithms or business logic.

Avoid commenting on things that are obvious from the code itself.

2.4. Formatting
Unify the use of indentation, spacing, and line breaks across the project.

Group related blocks of code into "paragraphs" to improve visual readability.

Team consistency is more important than personal preference.

3. Code Structure & Organization
   3.1. File & Module Splitting
   Keep files between 300-500 lines. If a file exceeds this, split it appropriately.

Separate files by concerns, such as data fetching, business logic, and UI rendering.

Extract generic logic (e.g., validation, formatting) into reusable utility functions.

3.2. Directory Structure
Organize the project with a logical structure, dividing folders by feature or domain.

Place a README.md in each folder to describe its role and contents.

Example Structure
src/
├── features/                          # High-level feature folder
│   ├── authentication/                # Sub-feature folder
│   │   ├── components/                # UI Components
│   │   │   ├── LoginForm.js
│   │   │   └── ProfilePage.js
│   │   ├── services/                  # Services like API integration
│   │   │   └── authAPI.js
│   │   │   └── README.md              # Describe all files and functions in this directory
│   │   ├── tests/
│   │   │   ├── LoginForm.test.js
│   │   │   └── README.md              # Describe how to run tests and their intent
│   │   └── README.md                  # Describe sub-feature behavior and specifications
│   └── another-feature/
│       └── ...
├── shared/                            # Code shared across multiple features
│   ├── components/                    # Shared UI Components
│   ├── utils/                         # Shared utility functions
│   └── hooks/                         # Shared custom hooks
└── README.md                          # Describe overall project structure and roles


3.3. Document Management
Always update the README.md files when code changes.

Code, tests, and documentation must always be managed as a three-piece set.

| Location | Description |
| src/README.md | Overall project structure, purpose, and folder overview. |
| src/features/feature-X/README.md | Overview of Feature X, list of sub-features, dependencies, etc. |
| src/features/.../services/README.md | Description of all files and functions within the directory (e.g., API specifications).|
| src/features/.../tests/README.md | How to run tests, coverage scope, and test intent. |

4. Security Measures
   4.1. Input Validation & Sanitization
   Validate all user input on both the client-side and server-side.

Use parameterized queries or an ORM to prevent SQL/NoSQL injection.

Sanitize data before rendering to prevent XSS (Cross-Site Scripting).

4.2. Authentication & Authorization
Protect sensitive routes with authentication middleware.

Implement proper authorization checks for data access and use role-based permissions.

Implement anti-CSRF tokens to mitigate Cross-Site Request Forgery.

4.3. API & Secrets Management
Implement rate limiting on authentication endpoints.

Set secure HTTP headers like CORS and Content-Security-Policy. Always use HTTPS.

Never hardcode secrets. Use environment variables or a secrets management service.

5. Performance & Reliability
   5.1. Error Handling
   Implement comprehensive error handling and catch specific error types.

Log errors with sufficient context for debugging.

Display user-friendly error messages in the UI.

Use try/catch blocks with async/await to handle network failures gracefully.

5.2. Performance Optimization
Cache or memoize expensive computation results.

Use virtualization for long lists, and implement code splitting and lazy loading for components.

When improving or refactoring functionality, always remove unused functions and variables to optimize memory usage.

Ensure that event listeners and timers are properly cleaned up when no longer needed to prevent memory leaks.

5.3. Database
Wrap related operations in transactions to ensure data consistency.

Create indexes for frequently queried fields. Avoid SELECT *.

Use a connection pool and close connections promptly.

6. Testing
   Cover critical business logic with Unit Tests.

Verify critical flows involving multiple components with Integration Tests.

Implement End-to-End (E2E) Tests for major user journeys.

7. Frontend-Specific Considerations
   7.1. State Management
   Choose a state management solution appropriate for the app's complexity (e.g., Context API, Redux, Zustand).

Avoid prop drilling. Keep state as close as possible to where it's needed.

7.2. Accessibility (a11y)
Use semantic HTML elements.

Add appropriate ARIA attributes to interactive elements to ensure keyboard navigation.

Maintain sufficient color contrast.

8. Prohibited Practices
   Implementing code that is not generic and only works for specific test cases.

Hardcoding magic numbers or strings with unclear purposes.

Leaving commented-out legacy code in the codebase.