package main

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/nbd-wtf/go-nostr"
)

// EggPet represents a pet in its initial state before naming
type EggPet struct {
	*BasePet
	ownerPubKey string
	createdAt   time.Time
	totem       *Totem
}

// NewEggPet creates a new pet in egg state
func NewEggPet(ownerPubKey string, totem *Totem) *EggPet {
	eggPet := &EggPet{
		BasePet:     NewBasePet("Egg"),
		ownerPubKey: ownerPubKey,
		createdAt:   time.Now(),
		totem:       totem,
	}

	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		eggPet.publishMetadataEvent(ctx)
	}()

	return eggPet
}

func (p *EggPet) Update() {
	// Do nothing - eggs don't decay
}

func (p *EggPet) PublishStatusEvent(ctx context.Context, publishFunc func(context.Context, *nostr.Event) error) error {
	// Do nothing - eggs don't publish status
	return nil
}

func (p *EggPet) publishMetadataEvent(ctx context.Context) {
	metadata := map[string]string{
		"name":  p.state.Name,
		"about": "I'm still an egg waiting to be named!",
	}

	metadataJSON, err := json.Marshal(metadata)
	if err != nil {
		fmt.Printf("Error creating metadata JSON: %v\n", err)
		return
	}

	ev := nostr.Event{
		PubKey:    p.publicKey,
		CreatedAt: nostr.Now(),
		Kind:      nostr.KindProfileMetadata,
		Tags:      nostr.Tags{{"p", p.ownerPubKey}},
		Content:   string(metadataJSON),
	}

	ev.Sign(p.privateKey)

	fmt.Printf("Publishing metadata event for egg: %s\n", ev.ID)
	err = p.totem.PublishEvent(ctx, &ev)
	if err != nil {
		fmt.Printf("Error publishing metadata: %v\n", err)
	} else {
		fmt.Printf("Published metadata for egg with ID: %s\n", ev.ID)
	}
}

func (p *EggPet) GetStateEmoji() string {
	return "🥚"
}

func (p *EggPet) HandleNaming(ctx context.Context, name string) Pet {
	fmt.Printf("Egg hatching into pet named: %s\n", name)

	basePet := NewBasePet(name)
	basePet.ownerPubKey = p.ownerPubKey
	basePet.privateKey = p.privateKey
	basePet.publicKey = p.publicKey
	basePet.state.Happiness = p.state.Happiness
	basePet.state.Energy = p.state.Energy
	basePet.state.LastFed = p.state.LastFed

	pet := &DefaultPet{
		BasePet: basePet,
		totem:   p.totem,
	}

	bgCtx := context.Background()
	go func() {
		ctx, cancel := context.WithTimeout(bgCtx, 10*time.Second)
		defer cancel()
		pet.publishMetadataEvent(ctx)
	}()

	return pet
}

func (p *EggPet) handleStoreEvent(ctx context.Context, evt *nostr.Event) {
	fmt.Printf("Egg notified of event: %s\n", evt.ID)
}

// The egg responds minimally to other events
func (p *EggPet) handleDeleteEvent(ctx context.Context, evt *nostr.Event) {
	// Minimal implementation for egg state
}

func (p *EggPet) handleQueryEvents(ctx context.Context, filter nostr.Filter) (nostr.Filter, error) {
	// Minimal implementation for egg state
	return filter, nil
}

func (p *EggPet) handleRejectEvent(ctx context.Context, evt *nostr.Event) (bool, string) {
	// Minimal implementation for egg state
	return false, ""
}

// GetOwnerPubKey returns the public key of the pet's owner
func (p *EggPet) GetOwnerPubKey() string {
	return p.ownerPubKey
}

// GetCreationTime returns when the egg was created
func (p *EggPet) GetCreationTime() time.Time {
	return p.createdAt
}
