"""Funções para adicionar/remover o cargo de assinante no Discord."""
import discord


class CargoNaoEncontrado(Exception):
    pass


async def adicionar_cargo(guild: discord.Guild, discord_id: str, role_id: int) -> None:
    role = guild.get_role(role_id)
    if role is None:
        raise CargoNaoEncontrado(f"Cargo {role_id} não encontrado no servidor {guild.id}")

    member = guild.get_member(int(discord_id))
    if member is None:
        member = await guild.fetch_member(int(discord_id))

    await member.add_roles(role, reason="Assinatura confirmada via Mercado Pago")


async def remover_cargo(guild: discord.Guild, discord_id: str, role_id: int) -> None:
    role = guild.get_role(role_id)
    if role is None:
        return

    try:
        member = guild.get_member(int(discord_id))
        if member is None:
            member = await guild.fetch_member(int(discord_id))
    except discord.NotFound:
        return

    if role in member.roles:
        await member.remove_roles(role, reason="Assinatura expirada")
