require('dotenv').config();
const { Client, GatewayIntentBits, REST, Routes, EmbedBuilder } = require('discord.js');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent
  ]
});

// ---------- SLASH COMMANDS ----------
const commands = [
  { name: 'ping', description: 'Check latency and get your user ID' },
  { name: 'status', description: 'Show bot health' },
  { name: 'uptime', description: 'Show uptime' },
  { name: 'commands', description: 'List all commands' },
  { name: 'echo', description: 'Repeat a message', options: [
    { name: 'message', type: 3, description: 'Text', required: true }
  ]},
  { name: 'exec', description: 'Run shell command (owner only)', options: [
    { name: 'command', type: 3, description: 'Command', required: true }
  ]},
  { name: 'restart', description: 'Restart bot (owner only)' }
];

client.once('clientReady', async () => {
  console.log(`✅ Logged in as ${client.user.tag}!`);

  const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
  try {
    await rest.put(Routes.applicationCommands(client.user.id), { body: commands });
    console.log('✅ Slash commands registered.');
  } catch (error) {
    console.error(error);
  }
});

// ---------- SLASH COMMAND HANDLER ----------
client.on('interactionCreate', async interaction => {
  if (!interaction.isChatInputCommand()) return;
  const { commandName, user, options } = interaction;

  if (commandName === 'ping') {
    await interaction.reply(`🏓 Pong! Your ID: ${user.id}`);
  } else if (commandName === 'status') {
    await interaction.reply('✅ Bot is online.');
  } else if (commandName === 'uptime') {
    await interaction.reply(`⏱️ ${Math.floor(process.uptime())}s`);
  } else if (commandName === 'commands') {
    const list = commands.map(c => `/${c.name}`).join(', ');
    await interaction.reply(`📋 ${list}`);
  } else if (commandName === 'echo') {
    await interaction.reply(`🔊 ${options.getString('message')}`);
  } else if (commandName === 'exec' || commandName === 'restart') {
    const ownerId = process.env.OWNER_ID;
    if (user.id !== ownerId) return interaction.reply({ content: '❌ No.', ephemeral: true });
    if (commandName === 'exec') {
      const { exec } = require('child_process');
      const cmd = options.getString('command');
      await interaction.reply(`⏳ running...`);
      exec(cmd, (err, stdout, stderr) => {
        const out = stdout || stderr || 'done';
        interaction.editReply(`\`\`\`\n${out.slice(0, 1900)}\n\`\`\``);
      });
    } else if (commandName === 'restart') {
      await interaction.reply('🔄 Restarting...');
      setTimeout(() => process.exit(0), 1000);
    }
  }
});

// ---------- TEXT COMMAND FALLBACK (for testing) ----------
client.on('messageCreate', async message => {
  if (message.author.bot) return;
  if (!message.content.startsWith('!')) return;
  const args = message.content.slice(1).trim().split(/ +/);
  const cmd = args.shift().toLowerCase();

  if (cmd === 'ping') {
    await message.reply(`🏓 Pong! Your ID: ${message.author.id}`);
  } else if (cmd === 'status') {
    await message.reply('✅ Bot is online.');
  } else if (cmd === 'uptime') {
    await message.reply(`⏱️ ${Math.floor(process.uptime())}s`);
  } else if (cmd === 'exec') {
    const ownerId = process.env.OWNER_ID;
    if (message.author.id !== ownerId) return message.reply('❌ No.');
    const { exec } = require('child_process');
    const cmdToRun = args.join(' ');
    await message.reply(`⏳ running...`);
    exec(cmdToRun, (err, stdout, stderr) => {
      const out = stdout || stderr || 'done';
      message.reply(`\`\`\`\n${out.slice(0, 1900)}\n\`\`\``);
    });
  }
});

client.login(process.env.DISCORD_TOKEN);
