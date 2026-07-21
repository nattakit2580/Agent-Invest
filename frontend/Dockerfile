FROM node:20-alpine
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build
RUN chown -R node:node /app
USER node
ENV NODE_ENV=production
EXPOSE 3000
CMD ["npm", "start"]
