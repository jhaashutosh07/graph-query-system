# Frontend Vite + React Docker Image
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Build for production
RUN npm run build

# Install serve to run production build
RUN npm install -g serve

# Start server
CMD ["serve", "-s", "dist", "-l", "3000"]
