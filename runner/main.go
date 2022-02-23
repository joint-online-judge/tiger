package main

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"time"

	"github.com/containerd/cgroups"
	"github.com/opencontainers/runtime-spec/specs-go"
)

func main() {
	shares := uint64(100)
	control, err := cgroups.New(cgroups.V1, cgroups.StaticPath("/test"), &specs.LinuxResources{
		CPU: &specs.LinuxCPU{
			Shares: &shares,
		},
	})
	if err != nil {
		panic(err)
	}
	defer control.Delete()
	if len(os.Args) < 2 {
		fmt.Println("usage: main <command>")
		os.Exit(1)
	}
	cmd := exec.Command(os.Args[1], os.Args[2:]...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	done := make(chan bool, 1)
	timeout_ms := 1000 * time.Millisecond
	start := time.Now()
	err = cmd.Start()
	if err != nil {
		panic(err)
	}
	pid := cmd.Process.Pid
	if err := control.Add(cgroups.Process{Pid: pid}); err != nil {
		panic(err)
	}
	go func(done chan bool) {
		if err = cmd.Wait(); err != nil {
			panic(err)
		}
		fmt.Printf("done in %v\n", time.Since(start))
		done <- true
	}(done)
	select {
	case <-done:
		fmt.Printf("stdout: %s\n", stdout.String())
		fmt.Printf("stderr: %s\n", stderr.String())
	case <-time.After(timeout_ms):
		fmt.Printf("timeout in %v\n", time.Since(start))
		cmd.Process.Kill()
		os.Exit(1)
	}
}
