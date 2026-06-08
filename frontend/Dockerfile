FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3000

# Dev server with hot-reload; API URL injected via VITE_API_URL at runtime.
CMD ["npm", "run", "dev"]
