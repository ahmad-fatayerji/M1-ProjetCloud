#!/usr/bin/env python3
"""Script de peuplement (seed) pour Tiny Instagram.

Usage basique:
  python seed.py --users 5 --posts 40 --follows-min 1 --follows-max 3

Paramètres:
  --users        Nombre d'utilisateurs à créer (user1 .. userN)
  --posts        Nombre total de posts à répartir
  --follows-min  Nombre minimum de follows par utilisateur
  --follows-max  Nombre maximum de follows par utilisateur
  --prefix       Préfixe des noms d'utilisateurs (default: user)
  --batch-size   Taille des batchs pour l'écriture des posts (default: 100)
  --dry-run      N'écrit rien, affiche seulement le plan

Le script est idempotent sur les utilisateurs (il ne recrée pas si existants) et ajoute simplement des posts supplémentaires.

ATTENTION: Ce script écrit directement dans Datastore du projet courant (gcloud config get-value project).
"""
from __future__ import annotations
import argparse
import random
import time
from datetime import datetime, timedelta
from google.cloud import datastore


def parse_args():
    p = argparse.ArgumentParser(description="Seed Datastore for Tiny Instagram")
    p.add_argument('--users', type=int, default=5)
    p.add_argument('--posts', type=int, default=30)
    p.add_argument('--follows-min', type=int, default=1)
    p.add_argument('--follows-max', type=int, default=3)
    p.add_argument('--prefix', type=str, default='user')
    p.add_argument('--batch-size', type=int, default=100, help='Taille des batchs pour les posts')
    p.add_argument('--dry-run', action='store_true')
    return p.parse_args()


def ensure_users(client: datastore.Client, names: list[str], dry: bool):
    created = 0
    for name in names:
        key = client.key('User', name)
        entity = client.get(key)
        if entity is None:
            entity = datastore.Entity(key)
            entity['follows'] = []
            if not dry:
                client.put(entity)
            created += 1
    return created


def assign_follows(client: datastore.Client, names: list[str], fmin: int, fmax: int, dry: bool):
    for name in names:
        key = client.key('User', name)
        entity = client.get(key)
        if entity is None:
            continue  # devrait exister
        # Générer un set de follows (exclure soi-même)
        others = [u for u in names if u != name]
        if not others:
            continue
        target_count = random.randint(min(fmin, len(others)), min(fmax, len(others)))
        selection = random.sample(others, target_count)
        # Fusion avec existants
        existing = set(entity.get('follows', []))
        new_set = sorted(existing.union(selection))
        entity['follows'] = new_set
        if not dry:
            client.put(entity)


def create_posts(client: datastore.Client, names: list[str], total_posts: int, dry: bool, batch_size: int = 100):
    """Créer les posts par batch pour améliorer les performances."""
    if not names or total_posts <= 0:
        return 0
    
    created = 0
    base_time = datetime.utcnow()
    
    print(f"[Posts] Création de {total_posts} posts par batch de {batch_size}...")
    
    # Créer tous les posts en mémoire d'abord
    all_posts = []
    for i in range(total_posts):
        author = random.choice(names)
        key = client.key('Post')
        post = datastore.Entity(key)
        # Décaler artificiellement le timestamp pour obtenir un tri naturel
        post['author'] = author
        post['content'] = f"Seed post {i+1} by {author}"
        post['created'] = base_time - timedelta(seconds=i)
        all_posts.append(post)
    
    # Envoyer par batch
    if not dry:
        total_batches = (len(all_posts) + batch_size - 1) // batch_size
        
        for i in range(0, len(all_posts), batch_size):
            batch = all_posts[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            print(f"  Batch {batch_num}/{total_batches} ({len(batch)} posts)...", end='', flush=True)
            
            try:
                client.put_multi(batch)
                created += len(batch)
                print(" ✓")
            except Exception as e:
                print(f" ✗ Erreur: {e}")
                # Continuer même en cas d'erreur
            
            # Petite pause tous les 10 batchs pour ne pas surcharger
            if batch_num % 10 == 0:
                time.sleep(0.5)
    else:
        created = total_posts  # En dry-run, on simule
    
    return created


def main():
    args = parse_args()
    client = datastore.Client()

    user_names = [f"{args.prefix}{i}" for i in range(1, args.users + 1)]

    print(f"[Seed] Utilisateurs ciblés: {user_names}")
    if args.dry_run:
        print("[Dry-Run] Aucune écriture ne sera effectuée.")

    # 1. Users
    new_users = ensure_users(client, user_names, args.dry_run)
    print(f"[Seed] Nouveaux utilisateurs créés: {new_users}")

    # 2. Follows
    assign_follows(client, user_names, args.follows_min, args.follows_max, args.dry_run)
    print("[Seed] Relations de suivi ajustées.")

    # 3. Posts (avec batch-size)
    created_posts = create_posts(client, user_names, args.posts, args.dry_run, args.batch_size)
    print(f"[Seed] Posts créés: {created_posts}")

    print("[Seed] Terminé.")


if __name__ == '__main__':
    main()