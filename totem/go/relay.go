package main

import (
	"context"
	"fmt"

	"github.com/fiatjaf/khatru"
	"github.com/nbd-wtf/go-nostr"
)

type RelayInfo struct {
	Name        string
	Description string
	PubKey      string
	Software    string
	Version     string
}

// Database defines the interface for storage operations
type Database interface {
	SaveEvent(ctx context.Context, evt *nostr.Event) error
	DeleteEvent(ctx context.Context, evt *nostr.Event) error
	QueryEvents(ctx context.Context, filter nostr.Filter) (chan *nostr.Event, error)
	CountEvents(ctx context.Context, filter nostr.Filter) (int64, error)
}

type TotemRelay struct {
	*khatru.Relay
	totem    *Totem
	database Database
}

func NewTotemRelay(info RelayInfo, totem *Totem, db Database) *TotemRelay {
	relay := &TotemRelay{
		Relay:    khatru.NewRelay(),
		totem:    totem,
		database: db,
	}

	// Configure relay info
	relay.Info.Name = info.Name
	relay.Info.Description = info.Description
	relay.Info.PubKey = info.PubKey
	relay.Info.Software = info.Software
	relay.Info.Version = info.Version

	// Set up hooks for relay operations
	relay.StoreEvent = append(relay.StoreEvent, relay.handleStoreEvent)
	relay.DeleteEvent = append(relay.DeleteEvent, relay.handleDeleteEvent)
	relay.QueryEvents = append(relay.QueryEvents, relay.handleQueryEvents)
	relay.CountEvents = append(relay.CountEvents, relay.handleCountEvents)
	relay.RejectEvent = append(relay.RejectEvent, func(ctx context.Context, event *nostr.Event) (reject bool, msg string) {
		return relay.handleRejectEvent(ctx, event)
	})

	// This is a direct connection to the handleStoreEvent method
	totem.SetPublishEventHook(func(ctx context.Context, evt *nostr.Event) error {
		return relay.handleStoreEvent(ctx, evt)
	})

	fmt.Println("TotemRelay initialized with hooks set up")
	return relay
}

func (r *TotemRelay) handleStoreEvent(ctx context.Context, evt *nostr.Event) error {
	err := r.database.SaveEvent(ctx, evt)
	if err != nil {
		fmt.Printf("Error storing event: %v\n", err)
		return err
	}

	fmt.Printf("Relay storing event: %s\n", evt.ID)

	go r.totem.handleStoreEvent(ctx, evt)

	return nil
}

func (r *TotemRelay) handleDeleteEvent(ctx context.Context, evt *nostr.Event) error {
	fmt.Printf("Relay deleting event: %s\n", evt.ID)

	err := r.database.DeleteEvent(ctx, evt)
	if err != nil {
		fmt.Printf("Error deleting event: %v\n", err)
		return err
	}

	go r.totem.handleDeleteEvent(ctx, evt)

	return nil
}

func (r *TotemRelay) handleQueryEvents(ctx context.Context, filter nostr.Filter) (chan *nostr.Event, error) {
	fmt.Printf("Relay querying events with filter: %+v\n", filter)

	modifiedFilter, _ := r.totem.handleQueryEvents(ctx, filter)

	return r.database.QueryEvents(ctx, modifiedFilter)
}

func (r *TotemRelay) handleCountEvents(ctx context.Context, filter nostr.Filter) (int64, error) {
	fmt.Printf("Relay counting events with filter: %+v\n", filter)

	modifiedFilter, _ := r.totem.handleQueryEvents(ctx, filter)

	return r.database.CountEvents(ctx, modifiedFilter)
}

func (r *TotemRelay) handleRejectEvent(ctx context.Context, evt *nostr.Event) (bool, string) {
	fmt.Printf("Relay checking if event should be rejected: %s\n", evt.ID)

	return r.totem.handleRejectEvent(ctx, evt)
}

func (r *TotemRelay) GetTotem() *Totem {
	return r.totem
}

func (r *TotemRelay) GetDatabase() Database {
	return r.database
}
