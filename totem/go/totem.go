package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/nbd-wtf/go-nostr"
)

// Totem is the central manager that coordinates between relay and pets
type Totem struct {
	pubKey string
	pets   map[string]Pet
	mutex  sync.RWMutex
}

type PetCreator interface {
	Pet
	GetOwnerPubKey() string
	GetCreationTime() time.Time
	HandleNaming(ctx context.Context, name string) Pet
}

func (t *Totem) NamePet(ctx context.Context, eggID string, name string) (Pet, error) {
	t.mutex.Lock()
	defer t.mutex.Unlock()

	// Find the egg
	egg, exists := t.pets[eggID]
	if !exists {
		return nil, fmt.Errorf("egg with ID %s not found", eggID)
	}

	// Ensure it's an egg pet
	eggPet, ok := egg.(PetCreator)
	if !ok {
		return nil, fmt.Errorf("pet with ID %s is not in egg state", eggID)
	}

	// Hatch the egg into a named pet
	namedPet := eggPet.HandleNaming(ctx, name)

	// Replace the egg with the named pet
	delete(t.pets, eggID)
	t.pets[name] = namedPet

	log.Printf("Egg %s hatched into pet named: %s", eggID, name)
	return namedPet, nil
}

func (t *Totem) CreatePet(ctx context.Context, ownerPubKey string) PetCreator {
	t.mutex.Lock()
	defer t.mutex.Unlock()

	// Create a new egg
	eggID := fmt.Sprintf("egg-%s-%d", ownerPubKey[:8], time.Now().Unix())
	egg := NewEggPet(ownerPubKey)

	// Register the egg with Totem
	t.pets[eggID] = egg
	log.Printf("Egg created for owner: %s with ID: %s", ownerPubKey, eggID)

	return egg
}

func (t *Totem) FindEggsByOwner(ownerPubKey string) []PetCreator {
	t.mutex.RLock()
	defer t.mutex.RUnlock()

	var eggs []PetCreator
	for _, pet := range t.pets {
		if eggPet, ok := pet.(PetCreator); ok {
			if eggPet.GetOwnerPubKey() == ownerPubKey {
				eggs = append(eggs, eggPet)
			}
		}
	}

	return eggs
}

func (t *Totem) processPetCreationEvent(ctx context.Context, evt *nostr.Event) bool {
	// Check if this is a tool execution request (kind 5910)
	if evt.Kind != 5910 {
		return false
	}

	// Look for the "c" tag with "execute-tool" value
	var isExecuteTool bool
	for _, tag := range evt.Tags {
		if len(tag) >= 2 && tag[0] == "c" && tag[1] == "execute-tool" {
			isExecuteTool = true
			break
		}
	}

	if !isExecuteTool {
		return false
	}

	// Parse the content as JSON
	var request struct {
		Name       string `json:"name"`
		Parameters struct {
			Name string `json:"name,omitempty"`
		} `json:"parameters"`
	}

	if err := json.Unmarshal([]byte(evt.Content), &request); err != nil {
		fmt.Printf("Error parsing pet creation event: %v\n", err)
		return false
	}

	// Check if this is a pet creation request
	if request.Name != "create_pet" {
		return false
	}

	fmt.Printf("Processing pet creation request from %s\n", evt.PubKey)

	// If no name is provided, create an egg
	if request.Parameters.Name == "" {
		t.CreatePet(ctx, evt.PubKey)
		fmt.Printf("Created new egg for user %s\n", evt.PubKey)
		return true
	}

	// If a name is provided, check if the user has an egg
	eggs := t.FindEggsByOwner(evt.PubKey)
	if len(eggs) == 0 {
		// No eggs found - user must create an egg first
		fmt.Printf("User %s tried to name a pet without an egg\n", evt.PubKey)
		return true // We still processed the event, but didn't create a pet
	}

	// User has an egg, so name it
	egg := eggs[0]
	eggID := fmt.Sprintf("egg-%s-%d", evt.PubKey[:8], egg.GetCreationTime().Unix())
	_, err := t.NamePet(ctx, eggID, request.Parameters.Name)
	if err != nil {
		fmt.Printf("Error naming egg: %v\n", err)
	} else {
		fmt.Printf("Successfully named egg to: %s\n", request.Parameters.Name)
	}

	return true
}

// NewTotem creates a new Totem instance
func NewTotem(pubKey string) *Totem {
	return &Totem{
		pubKey: pubKey,
		pets:   make(map[string]Pet),
	}
}

// RegisterPet adds a pet to the Totem's management
func (t *Totem) RegisterPet(p Pet) {
	t.mutex.Lock()
	defer t.mutex.Unlock()
	state := p.GetState()
	t.pets[state.Name] = p
	log.Printf("Pet registered: %s", state.Name)
}

// GetPubKey returns Totem's public key
func (t *Totem) GetPubKey() string {
	return t.pubKey
}

func (t *Totem) handleStoreEvent(ctx context.Context, evt *nostr.Event) {
	fmt.Printf("Totem notified of event: %s\n", evt.ID)

	// First, check if this is a pet creation event
	if t.processPetCreationEvent(ctx, evt) {
		fmt.Printf("Successfully processed pet creation event: %s\n", evt.ID)
		return
	}

	// If not a creation event, continue with standard event handling
	targetPet := t.findTargetPet(evt)
	if targetPet != nil {
		fmt.Printf("Notifying pet %s about event\n", targetPet.GetState().Name)
		targetPet.handleStoreEvent(ctx, evt)
	}

	fmt.Printf("Event content: %s\n", evt.Content)
}

// handleDeleteEvent notifies Totem and relevant pets about a deletion
func (t *Totem) handleDeleteEvent(ctx context.Context, evt *nostr.Event) {
	fmt.Printf("Totem notified of deletion: %s\n", evt.ID)

	targetPet := t.findTargetPet(evt)
	if targetPet != nil {
		fmt.Printf("Notifying pet %s about deletion\n", targetPet.GetState().Name)
		targetPet.handleDeleteEvent(ctx, evt)
	}
}

// handleQueryEvents allows Totem to suggest modifications to query filters
func (t *Totem) handleQueryEvents(ctx context.Context, filter nostr.Filter) (nostr.Filter, error) {
	modifiedFilter := filter

	t.mutex.RLock()
	defer t.mutex.RUnlock()

	// Let pets suggest filter modifications
	for _, pet := range t.pets {
		var err error
		modifiedFilter, err = pet.handleQueryEvents(ctx, modifiedFilter)
		if err != nil {
			return filter, nil // Ignore errors, use original filter
		}
	}

	return modifiedFilter, nil
}

// handleRejectEvent determines if an event should be rejected
func (t *Totem) handleRejectEvent(ctx context.Context, evt *nostr.Event) (bool, string) {
	fmt.Printf("Totem checking if event should be rejected: %s\n", evt.ID)

	// Check if any pet wants to reject this event
	targetPet := t.findTargetPet(evt)
	if targetPet != nil {
		return targetPet.handleRejectEvent(ctx, evt)
	}

	// No rejection by default
	return false, ""
}

// findTargetPet determines which pet should handle an event
func (t *Totem) findTargetPet(evt *nostr.Event) Pet {
	t.mutex.RLock()
	defer t.mutex.RUnlock()

	// For this simple implementation, just return the first pet
	// In a real implementation, you'd have logic to determine the target
	// based on tags, content, etc.
	if len(t.pets) > 0 {
		for _, pet := range t.pets {
			return pet
		}
	}

	return nil
}

// GetPets returns all registered pets
func (t *Totem) GetPets() []Pet {
	t.mutex.RLock()
	defer t.mutex.RUnlock()

	pets := make([]Pet, 0, len(t.pets))
	for _, p := range t.pets {
		pets = append(pets, p)
	}

	return pets
}
