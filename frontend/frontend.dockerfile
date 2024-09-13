# Use an official Node runtime as the base image
FROM node:18-alpine

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Set Generator ENV variable
ARG NEXT_PUBLIC_REPORT_GENERATOR_URL
ENV NEXT_PUBLIC_REPORT_GENERATOR_URL=$NEXT_PUBLIC_REPORT_GENERATOR_URL

# Build the Next.js application
RUN npm run build

# Expose the port the app runs on
EXPOSE $PORT

# Start the application
CMD ["sh", "-c", "npm start -- -p $PORT"]