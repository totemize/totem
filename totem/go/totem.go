package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sort"
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

	if eggPet.GetOwnerPubKey() == "" {
		return nil, fmt.Errorf("egg with pubkey %s has no owner", pubKey)
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

func (t *Totem) processTotemCommand(ctx context.Context, evt *nostr.Event) bool {
	// Validate event kind
	if evt.Kind != KindPetCommand {
		return false
	}

	// Validate command tag
	if !ValidateCommandTag(evt.Tags) {
		return false
	}

	// Parse command
	cmd, err := ParseCommand(evt.Content)
	if err != nil {
		fmt.Printf("Error parsing command: %v\n", err)
		return false
	}

	// Process command based on name
	switch cmd.Name {
	case CmdCreateEgg:
		return t.handleCreateEggCommand(ctx, evt, cmd.Parameters)
	case CmdNamePet:
		return t.handleNamePetCommand(ctx, evt, cmd.Parameters)
	default:
		fmt.Printf("Unknown command: %s\n", cmd.Name)
		return false
	}
}

func (t *Totem) handleCreateEggCommand(ctx context.Context, evt *nostr.Event, rawParams json.RawMessage) bool {
	_, err := ParseCreateEggParams(rawParams)
	if err != nil {
		fmt.Printf("Error parsing create_egg parameters: %v\n", err)
		return false
	}

	// Create new egg
	egg := t.CreatePet(ctx, evt.PubKey)
	fmt.Printf("Created new egg for user %s with pubkey %s\n",
		evt.PubKey, egg.GetPubKey())

	return true
}

func (t *Totem) handleNamePetCommand(ctx context.Context, evt *nostr.Event, rawParams json.RawMessage) bool {
	params, err := ParseNamePetParams(rawParams)
	if err != nil {
		fmt.Printf("Error parsing name_pet parameters: %v\n", err)
		return false
	}

	var targetEgg PetCreator

	// If pet_id is provided, find the egg with that ID
	if params.PetID != "" {
		pet, exists := t.pets[params.PetID]
		if !exists {
			fmt.Printf("Pet with ID %s not found\n", params.PetID)
			return true
		}

		eggPet, ok := pet.(PetCreator)
		if !ok {
			fmt.Printf("Pet with ID %s is not an egg\n", params.PetID)
			return true
		}

		// Security check: Verify that the event sender is the owner of the egg
		if eggPet.GetOwnerPubKey() != evt.PubKey {
			fmt.Printf("Security violation: User %s tried to name an egg owned by %s\n",
				evt.PubKey, eggPet.GetOwnerPubKey())
			return true
		}

		targetEgg = eggPet
	} else {
		// Find an egg owned by this user
		eggs := t.FindEggsByOwner(evt.PubKey)
		if len(eggs) == 0 {
			fmt.Printf("User %s tried to name a pet but has no eggs\n", evt.PubKey)
			return true
		}
		targetEgg = eggs[0]
	}

	// Name the pet
	_, err = t.NamePet(ctx, targetEgg.GetPubKey(), params.Name)
	if err != nil {
		fmt.Printf("Error naming egg: %v\n", err)
	} else {
		fmt.Printf("Successfully named egg with ID %s to: %s\n",
			targetEgg.GetPubKey(), params.Name)
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

	if t.processTotemCommand(ctx, evt) {
		fmt.Printf("Successfully processed totem command event: %s\n", evt.ID)
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

	// 1. First, check if the event has any p tags that match pet pubkeys
	for _, tag := range evt.Tags {
		if len(tag) >= 2 && tag[0] == "p" {
			taggedPubKey := tag[1]
			// Check if this pubkey matches any pet
			if pet, exists := t.pets[taggedPubKey]; exists {
				fmt.Printf("Pet %s is tagged in event %s\n", pet.GetState().Name, evt.ID)
				return pet
			}
		}
	}

	// 2. If no pet is tagged, check if the event sender owns a pet
	for _, pet := range t.pets {
		if pet.GetOwnerPubKey() == evt.PubKey {
			return pet
		}
	}

	// 3. If no pet owned by this user, pick a random pet (first non-egg pet for simplicity)
	for _, pet := range t.pets {
		// Skip eggs for random selection
		if _, isEgg := pet.(PetCreator); !isEgg {
			return pet
		}
	}

	// 4. If no non-egg pets, just return the first pet
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

	// Sort pets by public key to ensure stable order
	sort.Slice(pets, func(i, j int) bool {
		return pets[i].GetPubKey() < pets[j].GetPubKey()
	})

	return pets
}

// StartPetStatusUpdates begins periodic status updates for all pets
func (t *Totem) StartPetStatusUpdates(ctx context.Context) {
	go func() {
		ticker := time.NewTicker(2 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				t.mutex.RLock()
				pets := make([]Pet, 0, len(t.pets))
				for _, pet := range t.pets {
					// Skip eggs when collecting pets for status updates
					if _, isEgg := pet.(PetCreator); !isEgg {
						pets = append(pets, pet)
					}
				}
				t.mutex.RUnlock()

				// Publish status for each pet
				for _, pet := range pets {
					// Create a new context for each publish operation
					pubCtx, cancel := context.WithTimeout(ctx, 5*time.Second)

					// Use the pet's PublishStatusEvent method
					err := pet.PublishStatusEvent(pubCtx, t.publishEventHook)

					cancel()

					if err != nil {
						fmt.Printf("Error publishing status for pet %s: %v\n", pet.GetState().Name, err)
					}
				}
			}
		}
	}()
}
