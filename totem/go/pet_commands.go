package main

import (
	"encoding/json"
	"fmt"

	"github.com/nbd-wtf/go-nostr"
)

const (
	KindPetCommand = 5910
	TagCommand     = "c"
	TagExecuteTool = "execute-tool"

	// Command names
	CmdCreateEgg = "create_egg"
	CmdNamePet   = "name_pet"
)

// CommandRequest represents the standard format for all commands
type CommandRequest struct {
	Name       string          `json:"name"`
	Parameters json.RawMessage `json:"parameters"`
}

// CreateEggParams represents the parameters for create_egg command
type CreateEggParams struct {
	// No parameters needed for egg creation
}

// NamePetParams represents the parameters for name_pet command
type NamePetParams struct {
	PetID string `json:"pet_id"` // Optional
	Name  string `json:"name"`
}

// ValidateCommandTag ensures the command tag is present and correct
func ValidateCommandTag(tags nostr.Tags) bool {
	for _, tag := range tags {
		if len(tag) >= 2 && tag[0] == TagCommand && tag[1] == TagExecuteTool {
			return true
		}
	}
	return false
}

// ParseCommand parses a command from raw JSON content
func ParseCommand(content string) (*CommandRequest, error) {
	var cmd CommandRequest
	if err := json.Unmarshal([]byte(content), &cmd); err != nil {
		return nil, fmt.Errorf("invalid command format: %w", err)
	}
	return &cmd, nil
}

// ParseCreateEggParams parses parameters for create_egg command
func ParseCreateEggParams(rawParams json.RawMessage) (*CreateEggParams, error) {
	var params CreateEggParams
	if len(rawParams) > 0 {
		if err := json.Unmarshal(rawParams, &params); err != nil {
			return nil, fmt.Errorf("invalid create_egg parameters: %w", err)
		}
	}
	return &params, nil
}

// ParseNamePetParams parses parameters for name_pet command
func ParseNamePetParams(rawParams json.RawMessage) (*NamePetParams, error) {
	var params NamePetParams
	if err := json.Unmarshal(rawParams, &params); err != nil {
		return nil, fmt.Errorf("invalid name_pet parameters: %w", err)
	}

	if params.Name == "" {
		return nil, fmt.Errorf("name parameter is required")
	}

	return &params, nil
}
