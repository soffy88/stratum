FROM node:24
WORKDIR /app
RUN npm install -g pnpm@9 --registry https://registry.npmmirror.com \
    && pnpm config set registry https://registry.npmmirror.com
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
COPY .next/standalone ./
COPY .next/static ./.next/static
COPY public ./public
EXPOSE 3000
CMD ["node", "server.js"]
