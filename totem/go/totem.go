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

type Totem struct {
	pubKey           string
	pets             map[string]Pet
	mutex            sync.RWMutex
	publishEventHook func(context.Context, *nostr.Event) error
}

type PetCreator interface {
	Pet
	GetOwnerPubKey() string
	GetCreationTime() time.Time
	HandleNaming(ctx context.Context, name string) Pet
	publishMetadataEvent(ctx context.Context)
}

func (t *Totem) NamePet(ctx context.Context, pubKey string, name string) (Pet, error) {
	t.mutex.Lock()
	defer t.mutex.Unlock()

	egg, exists := t.pets[pubKey]
	if !exists {
		return nil, fmt.Errorf("egg with pubkey %s not found", pubKey)
	}

	eggPet, ok := egg.(PetCreator)
	if !ok {
		return nil, fmt.Errorf("pet with pubkey %s is not in egg state", pubKey)
	}

	namedPet := eggPet.HandleNaming(ctx, name)

	t.pets[pubKey] = namedPet

	log.Printf("Egg with pubkey %s hatched into pet named: %s",
		pubKey, name)

	return namedPet, nil
}

func (t *Totem) CreatePet(ctx context.Context, ownerPubKey string) PetCreator {
	t.mutex.Lock()
	defer t.mutex.Unlock()

	egg := NewEggPet(ownerPubKey, t)
	t.pets[egg.GetPubKey()] = egg
	log.Printf("Egg created for owner: %s with pubkey: %s", ownerPubKey, egg.GetPubKey())

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
		egg := t.CreatePet(ctx, evt.PubKey)
		fmt.Printf("Created new egg for user %s with pubkey %s\n",
			evt.PubKey, egg.GetPubKey())
		return true
	}

	// If a name is provided, check if the user has an egg
	eggs := t.FindEggsByOwner(evt.PubKey)
	if len(eggs) == 0 {
		fmt.Printf("User %s tried to name a pet without an egg\n", evt.PubKey)
		return true
	}

	// User has an egg, so name it
	egg := eggs[0]
	_, err := t.NamePet(ctx, egg.GetPubKey(), request.Parameters.Name)
	if err != nil {
		fmt.Printf("Error naming egg: %v\n", err)
	} else {
		fmt.Printf("Successfully named egg to: %s\n", request.Parameters.Name)
	}

	return true
}

func (t *Totem) PublishEvent(ctx context.Context, evt *nostr.Event) error {
	fmt.Printf("Totem publishing event from %s: %s\n", evt.PubKey, evt.ID)

	if t.publishEventHook != nil {
		return t.publishEventHook(ctx, evt)
	}

	return fmt.Errorf("publish event hook not set")
}

func (t *Totem) SetPublishEventHook(hook func(context.Context, *nostr.Event) error) {
	t.publishEventHook = hook
}

func NewTotem(pubKey string) *Totem {
	return &Totem{
		pubKey: pubKey,
		pets:   make(map[string]Pet),
	}
}

func (t *Totem) RegisterPet(p Pet) {
	t.mutex.Lock()
	defer t.mutex.Unlock()
	state := p.GetState()
	t.pets[state.Name] = p
	log.Printf("Pet registered: %s", state.Name)
}

func (t *Totem) GetPubKey() string {
	return t.pubKey
}

func (t *Totem) handleStoreEvent(ctx context.Context, evt *nostr.Event) {
	fmt.Printf("Totem notified of event: %s\n", evt.ID)

	if t.processPetCreationEvent(ctx, evt) {
		fmt.Printf("Successfully processed pet creation event: %s\n", evt.ID)
		return
	}

	targetPet := t.findTargetPet(evt)
	if targetPet != nil {
		fmt.Printf("Notifying pet %s about event\n", targetPet.GetState().Name)
		targetPet.handleStoreEvent(ctx, evt)
	}

	fmt.Printf("Event content: %s\n", evt.Content)
}

func (t *Totem) handleDeleteEvent(ctx context.Context, evt *nostr.Event) {
	fmt.Printf("Totem notified of deletion: %s\n", evt.ID)

	targetPet := t.findTargetPet(evt)
	if targetPet != nil {
		fmt.Printf("Notifying pet %s about deletion\n", targetPet.GetState().Name)
		targetPet.handleDeleteEvent(ctx, evt)
	}
}

func (t *Totem) handleQueryEvents(ctx context.Context, filter nostr.Filter) (nostr.Filter, error) {
	modifiedFilter := filter

	t.mutex.RLock()
	defer t.mutex.RUnlock()

	for _, pet := range t.pets {
		var err error
		modifiedFilter, err = pet.handleQueryEvents(ctx, modifiedFilter)
		if err != nil {
			return filter, nil
		}
	}

	return modifiedFilter, nil
}

func (t *Totem) handleRejectEvent(ctx context.Context, evt *nostr.Event) (bool, string) {
	fmt.Printf("Totem checking if event should be rejected: %s\n", evt.ID)

	targetPet := t.findTargetPet(evt)
	if targetPet != nil {
		return targetPet.handleRejectEvent(ctx, evt)
	}

	return false, ""
}

// findTargetPet determines which pet should handle an event
func (t *Totem) findTargetPet(evt *nostr.Event) Pet {
	t.mutex.RLock()
	defer t.mutex.RUnlock()

	// For this simple implementation, just return the first pet
	// In a real implementation, we will have logic to determine the target
	// based on tags, content, etc.
	if len(t.pets) > 0 {
		for _, pet := range t.pets {
			return pet
		}
	}

	return nil
}

func (t *Totem) GetPets() []Pet {
	t.mutex.RLock()
	defer t.mutex.RUnlock()

	pets := make([]Pet, 0, len(t.pets))
	for _, p := range t.pets {
		pets = append(pets, p)
	}

	return pets
}
